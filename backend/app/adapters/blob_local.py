"""BlobStore on a local directory (docker compose volume / dev). Not for multi-machine prod."""

import os
import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path

from ..core.blob_keys import validate_blob_key
from ..errors import BlobNotFoundError, InvalidBlobKeyError

CHUNK_SIZE = 64 * 1024


class LocalBlobStore:
    def __init__(self, root: str):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        validate_blob_key(key)
        path = (self.root / key).resolve()
        # Second line of defence: a symlink inside the root must not lead outside it.
        if not path.is_relative_to(self.root):
            raise InvalidBlobKeyError("Invalid storage key")
        return path

    def _existing(self, key: str) -> Path:
        path = self._path(key)
        if not path.is_file():
            raise BlobNotFoundError("File not found")
        return path

    def put_file(self, key: str, src_path: str, content_type: str) -> None:
        dest = self._path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        # Write to a temp file in the same directory, then rename: readers see the old
        # object or the new one, never a partial write. Temp names start with '.', which
        # no valid key can address.
        fd, tmp = tempfile.mkstemp(dir=dest.parent, prefix=".tmp-")
        try:
            with os.fdopen(fd, "wb") as out, open(src_path, "rb") as src:
                shutil.copyfileobj(src, out, CHUNK_SIZE)
            os.replace(tmp, dest)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    def get_to_path(self, key: str, dest_path: str) -> None:
        shutil.copyfile(self._existing(key), dest_path)

    def size(self, key: str) -> int:
        return self._existing(key).stat().st_size

    def open_range(self, key: str, start: int, end: int | None) -> Iterator[bytes]:
        path = self._existing(key)  # validate eagerly, before the caller starts streaming
        last = path.stat().st_size - 1
        stop = last if end is None else min(end, last)
        if start < 0 or start > stop:
            raise ValueError("Invalid byte range")
        return _read_range(path, start, stop)

    def presigned_get_url(self, key: str, ttl_s: int) -> str | None:
        self._path(key)
        return None  # local files are streamed by the API itself

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


def _read_range(path: Path, start: int, stop: int) -> Iterator[bytes]:
    remaining = stop - start + 1
    with path.open("rb") as f:
        f.seek(start)
        while remaining > 0:
            chunk = f.read(min(CHUNK_SIZE, remaining))
            if not chunk:
                return
            remaining -= len(chunk)
            yield chunk
