import os

import pytest

from app.adapters.blob_local import LocalBlobStore
from app.errors import BlobNotFoundError, InvalidBlobKeyError

KEY = "uploads/v1/source.mp4"


@pytest.fixture
def store(tmp_path):
    return LocalBlobStore(str(tmp_path / "root"))


@pytest.fixture
def src(tmp_path):
    def make(content: bytes, name: str = "src.bin") -> str:
        path = tmp_path / name
        path.write_bytes(content)
        return str(path)

    return make


def test_blob_round_trip_and_overwrite(store, src, tmp_path):
    store.put_file(KEY, src(b"first version"), "video/mp4")
    store.put_file(KEY, src(b"second", "b.bin"), "video/mp4")  # retry overwrites

    out = tmp_path / "out.bin"
    store.get_to_path(KEY, str(out))
    assert out.read_bytes() == b"second"
    assert store.size(KEY) == 6
    # Atomic writes leave no temp files behind.
    assert sorted(os.listdir(store.root / "uploads" / "v1")) == ["source.mp4"]


def test_blob_open_range(store, src):
    store.put_file(KEY, src(bytes(range(256)) * 1000), "video/mp4")  # 256 000 bytes

    assert b"".join(store.open_range(KEY, 0, 3)) == bytes([0, 1, 2, 3])
    assert b"".join(store.open_range(KEY, 255_998, None)) == bytes([254, 255])
    assert len(b"".join(store.open_range(KEY, 10, 200_009))) == 200_000  # multi-chunk
    assert b"".join(store.open_range(KEY, 255_999, 10**9)) == bytes([255])  # end clamped
    with pytest.raises(ValueError):
        store.open_range(KEY, 300_000, None)


def test_blob_missing_key_raises_not_found(store, tmp_path):
    for call in (
        lambda: store.size(KEY),
        lambda: store.get_to_path(KEY, str(tmp_path / "x")),
        lambda: store.open_range(KEY, 0, None),
    ):
        with pytest.raises(BlobNotFoundError):
            call()


def test_blob_delete_is_idempotent(store, src):
    store.put_file(KEY, src(b"x"), "video/mp4")
    store.delete(KEY)
    store.delete(KEY)
    with pytest.raises(BlobNotFoundError):
        store.size(KEY)


def test_blob_local_has_no_presigned_url(store):
    assert store.presigned_get_url(KEY, 300) is None


def test_blob_traversal_keys_never_touch_the_filesystem(store, src, tmp_path):
    with pytest.raises(InvalidBlobKeyError):
        store.put_file("../escaped.mp4", src(b"x"), "video/mp4")
    assert not (tmp_path / "escaped.mp4").exists()


def test_blob_symlink_out_of_root_is_refused(store, src, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("secret")
    os.symlink(outside, store.root / "link")

    with pytest.raises(InvalidBlobKeyError):
        store.size("link/secret.txt")
    with pytest.raises(InvalidBlobKeyError):
        store.put_file("link/evil.mp4", src(b"x"), "video/mp4")
    assert not (outside / "evil.mp4").exists()
