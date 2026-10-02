from collections.abc import Callable
from dataclasses import dataclass

from .adapters.blob_local import LocalBlobStore
from .adapters.blob_s3 import S3BlobStore, make_s3_client
from .adapters.db import PostgresHealthCheck, create_db_engine
from .adapters.ffprobe import FfprobeVideoProber
from .adapters.oauth_google import GoogleOAuthClient
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
from .core.ports import (
    BlobStore,
    HealthCheck,
    JobQueue,
    JobRepo,
    MediaDownloader,
    MediaInfoFetcher,
    OAuthProvider,
    ResultRepo,
    SessionRepo,
    UserRepo,
    VideoProber,
    VideoRepo,
)


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
    )
