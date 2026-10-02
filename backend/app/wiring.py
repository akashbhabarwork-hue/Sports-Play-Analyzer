from collections.abc import Callable
from dataclasses import asdict, dataclass

from .adapters.blob_local import LocalBlobStore
from .adapters.blob_s3 import S3BlobStore, make_s3_client
from .adapters.db import PostgresHealthCheck, create_db_engine
from .adapters.ffmpeg_video import FfmpegFrameReader, FfmpegVideoEncoder
from .adapters.ffprobe import FfprobeVideoProber
from .adapters.memory_rate_limiter import InMemoryRateLimiter
from .adapters.oauth_google import GoogleOAuthClient
from .adapters.onnx_detector import OnnxYoloxDetector
from .adapters.opencv_annotator import OpenCvFrameAnnotator
from .adapters.pg_queue import PostgresJobQueue
from .adapters.pg_repos import (
    PostgresJobRepo,
    PostgresResultRepo,
    PostgresSessionRepo,
    PostgresUserRepo,
    PostgresVideoRepo,
)
from .adapters.safe_http_fetcher import SafeHttpDownloader
from .adapters.ytdlp_fetcher import YtDlpMetadataFetcher
from .config import Settings
from .core.models import DetectorParams, MetricsParams, PipelineParams, RateLimits, TrackerParams
from .core.ports import (
    BlobStore,
    Detector,
    HealthCheck,
    JobQueue,
    JobRepo,
    MediaDownloader,
    MediaInfoFetcher,
    OAuthProvider,
    RateLimiter,
    ResultRepo,
    SessionRepo,
    UserRepo,
    VideoProber,
    VideoRepo,
)
from .services.process import PipelinePorts, ProcessConfig
from .services.submit import UploadLimits


@dataclass(frozen=True, slots=True)
class Container:
    settings: Settings
    health_check: HealthCheck
    users: UserRepo
    sessions: SessionRepo
    videos: VideoRepo
    jobs: JobRepo
    results: ResultRepo
    queue: JobQueue
    blobs: BlobStore
    prober: VideoProber
    media_info: MediaInfoFetcher
    downloader: MediaDownloader
    # None when Google login is not configured (local dev without credentials).
    oauth: OAuthProvider | None = None
    # Always set by build_container; None only in tests that don't exercise limits.
    rate_limiter: RateLimiter | None = None


def _local_blobs(settings: Settings) -> BlobStore:
    return LocalBlobStore(settings.blob_local_dir)


def _s3_blobs(settings: Settings) -> BlobStore:
    client = make_s3_client(
        settings.s3_endpoint_url,
        settings.s3_region,
        settings.s3_access_key_id,
        settings.s3_secret_access_key,
    )
    return S3BlobStore(client, settings.s3_bucket)


# Registry keyed by BLOB_BACKEND (validated in config.validate_settings).
BLOB_STORES: dict[str, Callable[[Settings], BlobStore]] = {"local": _local_blobs, "s3": _s3_blobs}


def tracker_params(settings: Settings) -> TrackerParams:
    return TrackerParams(
        high_thresh=settings.tracker_high_thresh,
        low_thresh=settings.tracker_low_thresh,
        match_iou=settings.tracker_iou_threshold,
        low_match_iou=settings.tracker_low_iou,
        max_age=settings.tracker_max_age,
        min_hits=settings.tracker_min_hits,
        min_box_area_rel=settings.min_box_area_rel,
    )


def metrics_params(settings: Settings) -> MetricsParams:
    return MetricsParams(
        jitter_px=settings.jitter_px,
        max_gap_frames=settings.tracker_max_age,
        heatmap_w=settings.heatmap_grid_w,
        heatmap_h=settings.heatmap_grid_h,
        possession_dist_ratio=settings.possession_dist_ratio,
        possession_min_frames=settings.possession_min_frames,
    )


def pipeline_params(settings: Settings) -> PipelineParams:
    return PipelineParams(
        sample_fps=settings.sample_fps,
        max_seconds=settings.max_video_seconds,
        max_frame_side=settings.max_frame_side,
        heartbeat_every_frames=settings.heartbeat_every_frames,
        team_sample_every=settings.team_sample_every,
        team_max_samples=settings.team_max_samples,
        team_min_separation=settings.team_min_separation,
    )


def detector_params(settings: Settings) -> DetectorParams:
    return DetectorParams(
        input_size=settings.detect_input_size,
        player_min_score=settings.tracker_low_thresh,  # tracker stage 2 needs weak boxes (D-021)
        ball_min_score=settings.ball_conf_threshold,
        nms_iou=settings.nms_threshold,
        max_candidates=settings.detect_max_candidates,
    )


def process_config(settings: Settings) -> ProcessConfig:
    tracker, metrics, detector = (
        tracker_params(settings),
        metrics_params(settings),
        detector_params(settings),
    )
    return ProcessConfig(
        pipeline=pipeline_params(settings),
        tracker=tracker,
        metrics=metrics,
        limits=UploadLimits(settings.max_upload_bytes, settings.max_video_seconds),
        lease_s=settings.lease_seconds,
        extra_config={
            "tracker": asdict(tracker),
            "metrics": asdict(metrics),
            "detector": {"model": "yolox_s", **asdict(detector)},
        },
        tmp_root=settings.upload_tmp_dir or None,
    )


def build_detector(settings: Settings) -> Detector:
    """Loads the model (~36 MB, a second or two). Only the worker calls this, never the web app."""
    return OnnxYoloxDetector(settings.model_path, detector_params(settings), settings.ort_threads)


def build_pipeline_ports(container: Container, detector: Detector) -> PipelinePorts:
    s = container.settings
    return PipelinePorts(
        queue=container.queue,
        videos=container.videos,
        blobs=container.blobs,
        prober=container.prober,
        media_info=container.media_info,
        downloader=container.downloader,
        frames=FfmpegFrameReader(),
        encoder=FfmpegVideoEncoder(crf=s.encode_crf, preset=s.encode_preset),
        detector=detector,
        annotator=OpenCvFrameAnnotator(),
    )


def build_container(settings: Settings) -> Container:
    engine = create_db_engine(settings.database_url)
    return Container(
        settings=settings,
        health_check=PostgresHealthCheck(engine),
        users=PostgresUserRepo(engine),
        sessions=PostgresSessionRepo(engine),
        videos=PostgresVideoRepo(engine),
        jobs=PostgresJobRepo(engine),
        results=PostgresResultRepo(engine),
        queue=PostgresJobQueue(engine),
        blobs=BLOB_STORES[settings.blob_backend](settings),
        prober=FfprobeVideoProber(),
        media_info=YtDlpMetadataFetcher(
            cookies_b64=settings.ytdlp_cookies_b64, proxy=settings.ytdlp_proxy
        ),
        downloader=SafeHttpDownloader(proxy=settings.ytdlp_proxy),
        oauth=(
            GoogleOAuthClient(settings.google_client_id, settings.google_client_secret)
            if settings.oauth_configured
            else None
        ),
        rate_limiter=InMemoryRateLimiter(
            RateLimits(settings.rate_limit_per_minute, settings.rate_limit_per_hour)
        ),
    )
