"""BlobStore on S3-compatible object storage (Tigris, Cloudflare R2, AWS S3) via boto3."""

import functools
import logging
from collections.abc import Callable, Iterator
from typing import Any, ParamSpec, TypeVar

import boto3
from boto3.exceptions import S3UploadFailedError
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from ..core.blob_keys import clamp_presign_ttl, validate_blob_key
from ..errors import BlobNotFoundError, ExternalServiceError

logger = logging.getLogger(__name__)

CHUNK_SIZE = 64 * 1024
NOT_FOUND_CODES = {"404", "NoSuchKey", "NotFound"}

P = ParamSpec("P")
R = TypeVar("R")


def s3_errors(fn: Callable[P, R]) -> Callable[P, R]:
    @functools.wraps(fn)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return fn(*args, **kwargs)
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") in NOT_FOUND_CODES:
                raise BlobNotFoundError("File not found") from e
            logger.error("object storage call failed", extra={"op": fn.__name__})
            raise ExternalServiceError("Storage operation failed") from e
        except (BotoCoreError, S3UploadFailedError) as e:
            # upload_file wraps the server error in boto3's S3UploadFailedError (not a
            # ClientError). Never log the text: it can include endpoint and signing details.
            logger.error("object storage unavailable", extra={"op": fn.__name__})
            raise ExternalServiceError("Storage operation failed") from e

    return wrapper


def make_s3_client(endpoint_url: str, region: str, access_key_id: str, secret_access_key: str):
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url or None,
        region_name=region or None,
        aws_access_key_id=access_key_id or None,
        aws_secret_access_key=secret_access_key or None,
        config=Config(
            signature_version="s3v4",
            retries={"max_attempts": 3, "mode": "standard"},
            # boto3 >= 1.36 adds CRC checksums to every upload by default; that is AWS-only.
            # Google Cloud Storage's S3 API rejects it (SignatureDoesNotMatch), as do other
            # S3-compatible stores. Send checksums only when an operation requires them.
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        ),
    )


class S3BlobStore:
    def __init__(self, client: Any, bucket: str):
        self.client = client
        self.bucket = bucket

    @s3_errors
    def put_file(self, key: str, src_path: str, content_type: str) -> None:
        # S3 PUTs are atomic: the object appears only once the upload completes.
        self.client.upload_file(
            src_path, self.bucket, validate_blob_key(key), ExtraArgs={"ContentType": content_type}
        )

    @s3_errors
    def get_to_path(self, key: str, dest_path: str) -> None:
        self.client.download_file(self.bucket, validate_blob_key(key), dest_path)

    @s3_errors
    def size(self, key: str) -> int:
        head = self.client.head_object(Bucket=self.bucket, Key=validate_blob_key(key))
        return int(head["ContentLength"])

    @s3_errors
    def open_range(self, key: str, start: int, end: int | None) -> Iterator[bytes]:
        if start < 0 or (end is not None and end < start):
            raise ValueError("Invalid byte range")
        byte_range = f"bytes={start}-" if end is None else f"bytes={start}-{end}"
        obj = self.client.get_object(
            Bucket=self.bucket, Key=validate_blob_key(key), Range=byte_range
        )
        return obj["Body"].iter_chunks(CHUNK_SIZE)

    @s3_errors
    def presigned_get_url(self, key: str, ttl_s: int) -> str | None:
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": validate_blob_key(key)},
            ExpiresIn=clamp_presign_ttl(ttl_s),
        )

    @s3_errors
    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=validate_blob_key(key))
