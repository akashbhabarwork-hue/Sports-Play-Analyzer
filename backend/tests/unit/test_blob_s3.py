from urllib.parse import parse_qs, urlparse

import pytest
from moto import mock_aws

from app.adapters.blob_s3 import S3BlobStore, make_s3_client
from app.errors import BlobNotFoundError, ExternalServiceError, InvalidBlobKeyError

BUCKET = "media"
KEY = "jobs/j1/annotated.mp4"


@pytest.fixture
def store():
    # moto intercepts boto3 in-process: no network, no real account.
    with mock_aws():
        # The same factory production uses (SigV4, retries); endpoint empty = AWS.
        client = make_s3_client("", "us-east-1", "testing", "testing")
        client.create_bucket(Bucket=BUCKET)
        yield S3BlobStore(client, BUCKET)


def test_blob_s3_round_trip_with_content_type(store, tmp_path):
    src = tmp_path / "in.mp4"
    src.write_bytes(b"video-bytes")

    store.put_file(KEY, str(src), "video/mp4")
    out = tmp_path / "out.mp4"
    store.get_to_path(KEY, str(out))

    assert out.read_bytes() == b"video-bytes"
    assert store.size(KEY) == 11
    head = store.client.head_object(Bucket=BUCKET, Key=KEY)
    assert head["ContentType"] == "video/mp4"


def test_blob_s3_open_range(store, tmp_path):
    src = tmp_path / "in.bin"
    src.write_bytes(bytes(range(100)))
    store.put_file(KEY, str(src), "application/octet-stream")

    assert b"".join(store.open_range(KEY, 10, 12)) == bytes([10, 11, 12])
    assert b"".join(store.open_range(KEY, 98, None)) == bytes([98, 99])


def test_blob_s3_missing_key_is_not_found(store, tmp_path):
    with pytest.raises(BlobNotFoundError):
        store.size(KEY)
    with pytest.raises(BlobNotFoundError):
        store.get_to_path(KEY, str(tmp_path / "x"))
    with pytest.raises(BlobNotFoundError):
        store.open_range(KEY, 0, None)


def test_blob_s3_presigned_url_expires_within_five_minutes(store):
    url = store.presigned_get_url(KEY, ttl_s=3600)

    query = parse_qs(urlparse(url).query)
    assert query["X-Amz-Expires"] == ["300"]
    assert KEY in urlparse(url).path


def test_blob_s3_delete_is_idempotent(store, tmp_path):
    src = tmp_path / "in.bin"
    src.write_bytes(b"x")
    store.put_file(KEY, str(src), "video/mp4")
    store.delete(KEY)
    store.delete(KEY)
    with pytest.raises(BlobNotFoundError):
        store.size(KEY)


def test_blob_s3_rejects_bad_keys_before_calling_s3(store, tmp_path):
    with pytest.raises(InvalidBlobKeyError):
        store.size("../other-bucket-object")


def test_blob_s3_backend_errors_are_wrapped(store):
    store.bucket = "bucket-that-does-not-exist"
    with pytest.raises(ExternalServiceError):
        store.delete(KEY)  # NoSuchBucket is a backend failure, not "file not found"


def test_blob_s3_failed_upload_is_a_storage_error_not_a_crash(store, tmp_path):
    # Regression (live): upload_file raises boto3's S3UploadFailedError, which used to escape
    # the wrapper and become a 500 "Something went wrong".
    src = tmp_path / "clip.mp4"
    src.write_bytes(b"data")
    store.bucket = "bucket-that-does-not-exist"
    with pytest.raises(ExternalServiceError):
        store.put_file(KEY, str(src), "video/mp4")


def test_s3_client_sends_checksums_only_when_required():
    # Regression (live): Google Cloud Storage rejected boto3's default upload checksums with
    # SignatureDoesNotMatch. Keep them opt-in for S3-compatible stores.
    config = make_s3_client("https://storage.googleapis.com", "auto", "k", "s").meta.config
    assert config.request_checksum_calculation == "when_required"
    assert config.response_checksum_validation == "when_required"
