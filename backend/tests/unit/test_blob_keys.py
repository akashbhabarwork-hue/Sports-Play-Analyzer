from uuid import UUID

import pytest

from app.core.blob_keys import (
    PRESIGNED_URL_MAX_TTL_S,
    annotated_key,
    clamp_presign_ttl,
    upload_key,
    validate_blob_key,
)
from app.errors import InvalidBlobKeyError

JOB = UUID("00000000-0000-0000-0000-000000000001")


@pytest.mark.parametrize(
    "key",
    [
        "uploads/abc/source.mp4",
        "jobs/00000000-0000-0000-0000-000000000001/annotated.mp4",
        "a",
        "a_b-c.d",
    ],
)
def test_valid_blob_keys(key):
    assert validate_blob_key(key) == key


@pytest.mark.parametrize(
    "key",
    [
        "",
        "..",
        "../etc/passwd",
        "uploads/../../etc/passwd",
        "uploads/./x",
        "/abs/path",
        "a//b",
        "a/",
        "a\\b",
        "..\\windows",
        "%2e%2e/x",
        "a/.hidden",
        "a/.tmp-123",
        "spaces are bad",
        "ünïcode",
        "a\x00b",
        "x" * 513,
    ],
)
def test_invalid_blob_keys_are_rejected(key):
    with pytest.raises(InvalidBlobKeyError):
        validate_blob_key(key)


def test_key_builders_are_deterministic_and_valid():
    assert annotated_key(JOB) == f"jobs/{JOB}/annotated.mp4"
    assert upload_key(JOB, ".MP4") == f"uploads/{JOB}/source.mp4"
    validate_blob_key(annotated_key(JOB))
    with pytest.raises(InvalidBlobKeyError):
        upload_key(JOB, "mp4/../../x")


def test_presign_ttl_is_capped_at_five_minutes():
    assert clamp_presign_ttl(3600) == PRESIGNED_URL_MAX_TTL_S == 300
    assert clamp_presign_ttl(60) == 60
    assert clamp_presign_ttl(0) == 1
