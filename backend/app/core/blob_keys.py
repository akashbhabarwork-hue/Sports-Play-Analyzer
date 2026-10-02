"""Blob key rules (pure). Every key that reaches a BlobStore is validated here first.

Keys are relative, '/'-separated segments of [A-Za-z0-9._-] that may not start with '.',
which rules out '.', '..' and hidden/temp names. Builders are deterministic so a retried
job overwrites its blobs instead of creating new ones.
"""

import re
from uuid import UUID

from ..errors import InvalidBlobKeyError

MAX_KEY_LENGTH = 512
PRESIGNED_URL_MAX_TTL_S = 300  # signed video links live at most 5 minutes
_SEGMENT = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9._-]*")
_EXTENSION = re.compile(r"[a-z0-9]{1,8}")


def validate_blob_key(key: str) -> str:
    if not key or len(key) > MAX_KEY_LENGTH:
        raise InvalidBlobKeyError("Invalid storage key")
    if not all(_SEGMENT.fullmatch(segment) for segment in key.split("/")):
        raise InvalidBlobKeyError("Invalid storage key")
    return key


def upload_key(video_id: UUID, extension: str) -> str:
    ext = extension.lower().lstrip(".")
    if not _EXTENSION.fullmatch(ext):
        raise InvalidBlobKeyError("Invalid file extension")
    return f"uploads/{video_id}/source.{ext}"


def annotated_key(job_id: UUID) -> str:
    return f"jobs/{job_id}/annotated.mp4"


def thumbnail_key(video_id: UUID) -> str:
    return f"videos/{video_id}/thumbnail.jpg"


def clamp_presign_ttl(ttl_s: int) -> int:
    return max(1, min(ttl_s, PRESIGNED_URL_MAX_TTL_S))
