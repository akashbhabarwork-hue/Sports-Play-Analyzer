import pytest

from app.adapters.blob_local import LocalBlobStore
from app.adapters.blob_s3 import S3BlobStore
from app.config import Settings, validate_settings
from app.wiring import BLOB_STORES

S3_OK = dict(s3_bucket="media", s3_access_key_id="key-id", s3_secret_access_key="key-secret")
AUTH_OK = dict(google_client_id="cid", google_client_secret="cs", session_secret="s" * 32)


def make(**overrides) -> Settings:
    return Settings(
        app_env="dev", app_origin="http://x", database_url="x", git_sha="t", **overrides
    )


def test_blob_backend_must_be_known():
    with pytest.raises(RuntimeError, match="BLOB_BACKEND must be one of: local, s3"):
        validate_settings(make(blob_backend="ftp"))


def test_blob_s3_requires_bucket_and_credentials_without_echoing_values():
    with pytest.raises(RuntimeError, match="S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY") as exc:
        validate_settings(make(blob_backend="s3", s3_bucket="media"))
    assert "media" not in str(exc.value)
    validate_settings(make(blob_backend="s3", **S3_OK))


def prod(**overrides) -> Settings:
    return Settings(
        app_env="production", app_origin="https://x", database_url="x", git_sha="t", **overrides
    )


def test_blob_local_is_refused_in_production():
    with pytest.raises(RuntimeError, match="must be s3 in production"):
        validate_settings(prod(blob_backend="local", **AUTH_OK))
    validate_settings(prod(blob_backend="s3", **AUTH_OK, **S3_OK))


def test_blob_registry_builds_the_configured_backend(tmp_path):
    local = BLOB_STORES["local"](make(blob_local_dir=str(tmp_path / "b")))
    s3 = BLOB_STORES["s3"](make(blob_backend="s3", s3_region="us-east-1", **S3_OK))
    assert isinstance(local, LocalBlobStore) and (tmp_path / "b").is_dir()
    assert isinstance(s3, S3BlobStore) and s3.bucket == "media"
    assert set(BLOB_STORES) == {"local", "s3"}
