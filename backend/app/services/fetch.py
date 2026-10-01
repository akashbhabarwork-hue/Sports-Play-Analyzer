"""Worker fetch stage for URL sources (called by process_job, T-062)."""

import logging
import os
import tempfile

from ..core.blob_keys import upload_key
from ..core.models import Video
from ..core.ports import BlobStore, MediaDownloader, MediaInfoFetcher, VideoProber, VideoRepo
from ..core.video_rules import check_remote_media
from .submit import UploadLimits, validate_video_file

logger = logging.getLogger(__name__)


def fetch_url_video(
    videos: VideoRepo,
    blobs: BlobStore,
    metadata: MediaInfoFetcher,
    downloader: MediaDownloader,
    prober: VideoProber,
    video: Video,
    limits: UploadLimits,
    tmp_root: str | None = None,
) -> str:
    """Download a URL-sourced video into blob storage; returns its storage key.

    Order: metadata (reject long/live before any bytes) → SSRF-guarded download with byte
    cap → the same content checks as uploads (sniff + ffprobe + limits) → store → record.
    Idempotent on retry: the key is derived from the video id, so a rerun overwrites.
    """
    if video.source_type != "url" or not video.source_url:
        raise ValueError("fetch_url_video needs a URL-sourced video")

    info = metadata.fetch_info(video.source_url)
    media_url = check_remote_media(info, limits.max_duration_s)

    with tempfile.TemporaryDirectory(dir=tmp_root, prefix="fetch-") as tmp:
        path = os.path.join(tmp, "source")
        size = downloader.download(media_url, info.http_headers, path, limits.max_bytes)
        container, probe = validate_video_file(path, prober, limits.max_duration_s)
        key = upload_key(video.id, container.extension)
        blobs.put_file(key, path, container.content_type)
    try:
        videos.set_media_for_worker(
            video.id, key, size, probe.duration_s, probe.width, probe.height, probe.fps or 0.0
        )
    except BaseException:
        blobs.delete(key)
        raise
    logger.info("url video fetched", extra={"video_id": str(video.id), "bytes": size})
    return key
