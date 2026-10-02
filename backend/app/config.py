import os
import socket
from dataclasses import dataclass

APP_ENV = os.getenv("APP_ENV", "dev")
APP_ORIGIN = os.getenv("APP_ORIGIN", "http://localhost:8000")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://app:app@localhost:5432/app")
GIT_SHA = os.getenv("GIT_SHA", "unknown")
# Built SPA directory served by FastAPI; the Docker image sets this to /app/backend/static
STATIC_DIR = os.getenv(
    "STATIC_DIR",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../../frontend/dist")),
)

# ---- job queue ----
# A claimed job is held for LEASE_SECONDS; the worker's heartbeat extends it. If the worker
# dies, the lease lapses and another worker reclaims the job (up to jobs.max_attempts).
LEASE_SECONDS = int(os.getenv("LEASE_SECONDS", "60"))
WORKER_ID = os.getenv("WORKER_ID", f"{socket.gethostname()}-{os.getpid()}")

# ---- auth ----
# Secrets have no usable default: in production load_settings() refuses to start without
# them; in dev, /auth/login answers "not configured" instead. Real values live only in .env
# or host secrets.
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
SESSION_SECRET = os.getenv("SESSION_SECRET", "")
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() == "true"
SESSION_TTL_DAYS = int(os.getenv("SESSION_TTL_DAYS", "7"))
# Extra origins allowed to send unsafe requests (CSRF check), comma-separated. APP_ORIGIN is
# always trusted; local dev adds the Vite server, e.g. http://localhost:5173.
TRUSTED_ORIGINS = tuple(o.strip() for o in os.getenv("TRUSTED_ORIGINS", "").split(",") if o.strip())

# ---- storage ----
# local: a directory (compose volume / dev). s3: Tigris, R2 or AWS — required in production
# because web and worker run on different machines and cannot share a disk.
BLOB_BACKEND = os.getenv("BLOB_BACKEND", "local")
BLOB_LOCAL_DIR = os.getenv(
    "BLOB_LOCAL_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "../../blobs"))
)
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "")
S3_BUCKET = os.getenv("S3_BUCKET", "")
S3_REGION = os.getenv("S3_REGION", "")
S3_ACCESS_KEY_ID = os.getenv("S3_ACCESS_KEY_ID", "")
S3_SECRET_ACCESS_KEY = os.getenv("S3_SECRET_ACCESS_KEY", "")
BLOB_BACKENDS = ("local", "s3")

# ---- ingestion limits ----
MAX_UPLOAD_SIZE_BYTES = int(os.getenv("MAX_UPLOAD_SIZE_BYTES", str(100 * 1024 * 1024)))
MAX_VIDEO_DURATION_SECONDS = int(os.getenv("MAX_VIDEO_DURATION_SECONDS", "60"))
# Per-request temp dirs for uploads live here (default: the system temp dir).
UPLOAD_TMP_DIR = os.getenv("UPLOAD_TMP_DIR", "")

# ---- YouTube fetch (optional mitigations for datacenter blocking, D-010) ----
# Base64 of a Netscape cookies.txt from a throwaway account; written to a 0600 temp file
# per fetch and deleted afterwards. Proxy URL is used for both yt-dlp and the download.
# Secrets: never logged, never committed.
YTDLP_COOKIES_B64 = os.getenv("YTDLP_COOKIES_B64", "")
YTDLP_PROXY = os.getenv("YTDLP_PROXY", "")

# ---- video decode/encode (adapters/ffmpeg_video.py) ----
# Frames analysed per second of video; the annotated output also plays at this rate.
SAMPLE_FPS = float(os.getenv("SAMPLE_FPS", "5"))
# Decoded frames are scaled so their long side is at most this (memory + detector cost).
MAX_FRAME_SIDE = int(os.getenv("MAX_FRAME_SIDE", "1280"))
# libx264 quality (lower = better, bigger) and speed preset for the annotated video.
ENCODE_CRF = int(os.getenv("ENCODE_CRF", "26"))
ENCODE_PRESET = os.getenv("ENCODE_PRESET", "veryfast")
ENCODE_PRESETS = ("ultrafast", "superfast", "veryfast", "faster", "fast", "medium")

# ---- worker pass (services/process.py) ----
# Heartbeat (extends the lease, writes progress) every N sampled frames; 10 at ~6 fps ≈ 2 s,
# far inside LEASE_SECONDS.
HEARTBEAT_EVERY_FRAMES = int(os.getenv("HEARTBEAT_EVERY_FRAMES", "10"))
# Jersey-colour samples for the team split: every N sampled frames, at most M per player.
TEAM_SAMPLE_EVERY = int(os.getenv("TEAM_SAMPLE_EVERY", "5"))
TEAM_MAX_SAMPLES = int(os.getenv("TEAM_MAX_SAMPLES", "20"))

# ---- detection (adapters/onnx_detector.py, core/detection.py) ----
# Pretrained YOLOX-S (Apache-2.0); the Docker image downloads it and checks its sha256.
MODEL_PATH = os.getenv(
    "MODEL_PATH",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../../models/yolox_s.onnx")),
)
# Square model input in pixels (multiple of 32). Smaller = faster, misses small players/ball.
DETECT_INPUT_SIZE = int(os.getenv("DETECT_INPUT_SIZE", "640"))
# Players are kept down to TRACKER_LOW_THRESH (tracker stage 2, D-021). The ball is small and
# blurry, so it gets its own, lower bar; at most one ball per frame is kept.
BALL_CONF_THRESHOLD = float(os.getenv("BALL_CONF_THRESHOLD", "0.15"))
NMS_THRESHOLD = float(os.getenv("NMS_THRESHOLD", "0.45"))
DETECT_MAX_CANDIDATES = int(os.getenv("DETECT_MAX_CANDIDATES", "300"))
# ONNX Runtime CPU threads; 0 lets ONNX Runtime pick (one per core).
ORT_THREADS = int(os.getenv("ORT_THREADS", "0"))

# ---- tracking (ByteTrack-style, core/tracking.py) ----
# Detections scoring >= TRACKER_HIGH_THRESH are matched first and may start new tracks; those
# between TRACKER_LOW_THRESH and it only keep existing tracks alive (partly hidden players).
# Ages and hit counts are in *sampled* frames (SAMPLE_FPS), not video frames.
TRACKER_HIGH_THRESH = float(os.getenv("TRACKER_HIGH_THRESH", "0.5"))
TRACKER_LOW_THRESH = float(os.getenv("TRACKER_LOW_THRESH", "0.1"))
TRACKER_IOU_THRESHOLD = float(os.getenv("TRACKER_IOU_THRESHOLD", "0.3"))
TRACKER_LOW_IOU = float(os.getenv("TRACKER_LOW_IOU", "0.5"))
TRACKER_MAX_AGE = int(os.getenv("TRACKER_MAX_AGE", "10"))
TRACKER_MIN_HITS = int(os.getenv("TRACKER_MIN_HITS", "3"))
# Boxes smaller than this fraction of the frame area are ignored (crowd, far-away noise).
MIN_BOX_AREA_REL = float(os.getenv("MIN_BOX_AREA_REL", "0.0005"))

# ---- metrics (core/metrics.py, heatmap.py, possession.py) ----
# Feet movements under JITTER_PX pixels are detector wobble, not running.
JITTER_PX = float(os.getenv("JITTER_PX", "2.0"))
HEATMAP_GRID_W = int(os.getenv("HEATMAP_GRID_W", "32"))
HEATMAP_GRID_H = int(os.getenv("HEATMAP_GRID_H", "18"))
# A player "has" the ball when it is within this many box heights of their feet, for at
# least POSSESSION_MIN_FRAMES sampled frames in a row.
POSSESSION_DIST_RATIO = float(os.getenv("POSSESSION_DIST_RATIO", "0.5"))
POSSESSION_MIN_FRAMES = int(os.getenv("POSSESSION_MIN_FRAMES", "3"))

# ---- teams (core/teams.py) ----
# Distance between the two jersey-colour cluster centres (HSV cone units, 0..~2) below which
# the kits are considered indistinguishable and every player is labelled "unknown".
TEAM_MIN_SEPARATION = float(os.getenv("TEAM_MIN_SEPARATION", "0.2"))

REQUIRED_IN_PRODUCTION = ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "SESSION_SECRET")


@dataclass(frozen=True, slots=True)
class Settings:
    app_env: str
    app_origin: str
    database_url: str
    git_sha: str
    static_dir: str = ""
    lease_seconds: int = 60
    worker_id: str = "worker"
    google_client_id: str = ""
    google_client_secret: str = ""
    session_secret: str = ""
    cookie_secure: bool = True
    session_ttl_days: int = 7
    trusted_origins: tuple[str, ...] = ()
    blob_backend: str = "local"
    blob_local_dir: str = ""
    s3_endpoint_url: str = ""
    s3_bucket: str = ""
    s3_region: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    max_upload_bytes: int = 100 * 1024 * 1024
    max_video_seconds: int = 60
    upload_tmp_dir: str = ""
    ytdlp_cookies_b64: str = ""
    ytdlp_proxy: str = ""
    sample_fps: float = 5.0
    max_frame_side: int = 1280
    encode_crf: int = 26
    encode_preset: str = "veryfast"
    heartbeat_every_frames: int = 10
    team_sample_every: int = 5
    team_max_samples: int = 20
    model_path: str = ""
    detect_input_size: int = 640
    ball_conf_threshold: float = 0.15
    nms_threshold: float = 0.45
    detect_max_candidates: int = 300
    ort_threads: int = 0
    tracker_high_thresh: float = 0.5
    tracker_low_thresh: float = 0.1
    tracker_iou_threshold: float = 0.3
    tracker_low_iou: float = 0.5
    tracker_max_age: int = 10
    tracker_min_hits: int = 3
    min_box_area_rel: float = 0.0005
    jitter_px: float = 2.0
    heatmap_grid_w: int = 32
    heatmap_grid_h: int = 18
    possession_dist_ratio: float = 0.5
    possession_min_frames: int = 3
    team_min_separation: float = 0.2

    @property
    def oauth_configured(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret and self.session_secret)

    @property
    def session_cookie_name(self) -> str:
        # The __Host- prefix makes browsers require Secure, Path=/ and no Domain.
        return "__Host-sid" if self.cookie_secure else "sid"

    @property
    def csrf_trusted_origins(self) -> frozenset[str]:
        origins = (self.app_origin, *self.trusted_origins)
        return frozenset(o.rstrip("/").lower() for o in origins if o)

    @property
    def oauth_redirect_uri(self) -> str:
        # Built from config, never from request headers, so a proxy cannot spoof it.
        return f"{self.app_origin.rstrip('/')}/auth/callback"


def validate_settings(settings: Settings) -> None:
    """Fail fast on bad config. Messages name settings, never their values."""
    if settings.blob_backend not in BLOB_BACKENDS:
        raise RuntimeError(f"BLOB_BACKEND must be one of: {', '.join(BLOB_BACKENDS)}")
    s3_values = {
        "S3_BUCKET": settings.s3_bucket,
        "S3_ACCESS_KEY_ID": settings.s3_access_key_id,
        "S3_SECRET_ACCESS_KEY": settings.s3_secret_access_key,
    }
    if settings.blob_backend == "s3":
        missing_s3 = [name for name, value in s3_values.items() if not value]
        if missing_s3:
            raise RuntimeError(
                f"Missing required settings for BLOB_BACKEND=s3: {', '.join(missing_s3)}"
            )
    validate_video_settings(settings)
    validate_tracker_settings(settings)
    validate_metrics_settings(settings)
    if settings.app_env != "production":
        return
    if settings.blob_backend != "s3":
        raise RuntimeError("BLOB_BACKEND must be s3 in production (web and worker share no disk)")
    values = {
        "GOOGLE_CLIENT_ID": settings.google_client_id,
        "GOOGLE_CLIENT_SECRET": settings.google_client_secret,
        "SESSION_SECRET": settings.session_secret,
    }
    missing = [name for name in REQUIRED_IN_PRODUCTION if not values[name]]
    if missing:
        raise RuntimeError(f"Missing required settings in production: {', '.join(missing)}")


def validate_video_settings(settings: Settings) -> None:
    if not 0 < settings.sample_fps <= 30:
        raise RuntimeError("SAMPLE_FPS must be in (0, 30]")
    if not 64 <= settings.max_frame_side <= 4096:
        raise RuntimeError("MAX_FRAME_SIDE must be between 64 and 4096")
    if not 0 <= settings.encode_crf <= 51:
        raise RuntimeError("ENCODE_CRF must be between 0 and 51")
    if settings.encode_preset not in ENCODE_PRESETS:
        raise RuntimeError(f"ENCODE_PRESET must be one of: {', '.join(ENCODE_PRESETS)}")
    if not (64 <= settings.detect_input_size <= 1280 and settings.detect_input_size % 32 == 0):
        raise RuntimeError("DETECT_INPUT_SIZE must be a multiple of 32 between 64 and 1280")
    if not (0 < settings.ball_conf_threshold <= 1 and 0 < settings.nms_threshold <= 1):
        raise RuntimeError("BALL_CONF_THRESHOLD and NMS_THRESHOLD must be in (0, 1]")
    if settings.detect_max_candidates < 1 or settings.ort_threads < 0:
        raise RuntimeError("DETECT_MAX_CANDIDATES must be >= 1 and ORT_THREADS >= 0")
    if min(settings.heartbeat_every_frames, settings.team_sample_every) < 1:
        raise RuntimeError("HEARTBEAT_EVERY_FRAMES and TEAM_SAMPLE_EVERY must be >= 1")
    if settings.team_max_samples < 1:
        raise RuntimeError("TEAM_MAX_SAMPLES must be >= 1")


def validate_tracker_settings(settings: Settings) -> None:
    if not 0 < settings.tracker_low_thresh < settings.tracker_high_thresh <= 1:
        raise RuntimeError("Need 0 < TRACKER_LOW_THRESH < TRACKER_HIGH_THRESH <= 1")
    if not (0 < settings.tracker_iou_threshold <= 1 and 0 < settings.tracker_low_iou <= 1):
        raise RuntimeError("TRACKER_IOU_THRESHOLD and TRACKER_LOW_IOU must be in (0, 1]")
    if settings.tracker_max_age < 1 or settings.tracker_min_hits < 1:
        raise RuntimeError("TRACKER_MAX_AGE and TRACKER_MIN_HITS must be at least 1")
    if not 0 <= settings.min_box_area_rel < 1:
        raise RuntimeError("MIN_BOX_AREA_REL must be in [0, 1)")


def validate_metrics_settings(settings: Settings) -> None:
    if settings.jitter_px < 0:
        raise RuntimeError("JITTER_PX must be >= 0")
    if not (1 <= settings.heatmap_grid_w <= 256 and 1 <= settings.heatmap_grid_h <= 256):
        raise RuntimeError("HEATMAP_GRID_W and HEATMAP_GRID_H must be between 1 and 256")
    if settings.possession_dist_ratio <= 0 or settings.possession_min_frames < 1:
        raise RuntimeError("POSSESSION_DIST_RATIO must be > 0 and POSSESSION_MIN_FRAMES >= 1")
    if settings.team_min_separation < 0:
        raise RuntimeError("TEAM_MIN_SEPARATION must be >= 0")


def load_settings() -> Settings:
    settings = Settings(
        app_env=APP_ENV,
        app_origin=APP_ORIGIN,
        database_url=DATABASE_URL,
        git_sha=GIT_SHA,
        static_dir=STATIC_DIR,
        lease_seconds=LEASE_SECONDS,
        worker_id=WORKER_ID,
        google_client_id=GOOGLE_CLIENT_ID,
        google_client_secret=GOOGLE_CLIENT_SECRET,
        session_secret=SESSION_SECRET,
        cookie_secure=COOKIE_SECURE,
        session_ttl_days=SESSION_TTL_DAYS,
        trusted_origins=TRUSTED_ORIGINS,
        blob_backend=BLOB_BACKEND,
        blob_local_dir=BLOB_LOCAL_DIR,
        s3_endpoint_url=S3_ENDPOINT_URL,
        s3_bucket=S3_BUCKET,
        s3_region=S3_REGION,
        s3_access_key_id=S3_ACCESS_KEY_ID,
        s3_secret_access_key=S3_SECRET_ACCESS_KEY,
        max_upload_bytes=MAX_UPLOAD_SIZE_BYTES,
        max_video_seconds=MAX_VIDEO_DURATION_SECONDS,
        upload_tmp_dir=UPLOAD_TMP_DIR,
        ytdlp_cookies_b64=YTDLP_COOKIES_B64,
        ytdlp_proxy=YTDLP_PROXY,
        sample_fps=SAMPLE_FPS,
        max_frame_side=MAX_FRAME_SIDE,
        encode_crf=ENCODE_CRF,
        encode_preset=ENCODE_PRESET,
        heartbeat_every_frames=HEARTBEAT_EVERY_FRAMES,
        team_sample_every=TEAM_SAMPLE_EVERY,
        team_max_samples=TEAM_MAX_SAMPLES,
        model_path=MODEL_PATH,
        detect_input_size=DETECT_INPUT_SIZE,
        ball_conf_threshold=BALL_CONF_THRESHOLD,
        nms_threshold=NMS_THRESHOLD,
        detect_max_candidates=DETECT_MAX_CANDIDATES,
        ort_threads=ORT_THREADS,
        tracker_high_thresh=TRACKER_HIGH_THRESH,
        tracker_low_thresh=TRACKER_LOW_THRESH,
        tracker_iou_threshold=TRACKER_IOU_THRESHOLD,
        tracker_low_iou=TRACKER_LOW_IOU,
        tracker_max_age=TRACKER_MAX_AGE,
        tracker_min_hits=TRACKER_MIN_HITS,
        min_box_area_rel=MIN_BOX_AREA_REL,
        jitter_px=JITTER_PX,
        heatmap_grid_w=HEATMAP_GRID_W,
        heatmap_grid_h=HEATMAP_GRID_H,
        possession_dist_ratio=POSSESSION_DIST_RATIO,
        possession_min_frames=POSSESSION_MIN_FRAMES,
        team_min_separation=TEAM_MIN_SEPARATION,
    )
    validate_settings(settings)
    return settings
