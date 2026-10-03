---
name: upload-validation
description: Validates uploaded video files by content not extension, streaming size limit (100 MB), magic-byte sniffing for MP4/MOV/WebM/MKV/AVI, ffprobe decode and duration checks (60 s), clean error codes (UNSUPPORTED_FORMAT, CORRUPT_FILE, DURATION_EXCEEDED, 413) and guaranteed temp-file cleanup. Use for the upload endpoint and any file ingestion.
---

# Upload validation

## Order of checks (cheap → expensive)
1. `Content-Length` header > `MAX_UPLOAD_MB` + 1 MB multipart overhead → 413 immediately.
2. Copy the `UploadFile` to a temp file in 1 MB chunks, counting bytes; > limit → 413 (handles
   missing/lying Content-Length). Never `await file.read()` the whole thing.
3. Sniff first 16 bytes (pure function `core/file_sniff.py`):
```python
def sniff_video_container(head: bytes) -> str | None:
    if len(head) >= 12 and head[4:8] == b"ftyp":
        return "mp4"                       # MP4 / MOV / M4V / 3GP family
    if head[:4] == b"\x1a\x45\xdf\xa3":
        return "matroska"                  # MKV / WebM
    if head[:4] == b"RIFF" and head[8:12] == b"AVI ":
        return "avi"
    return None
```
   None → 415 `UNSUPPORTED_FORMAT` "Only MP4, MOV, WebM, MKV or AVI videos are supported."
4. `ffprobe` (argument list, timeout 15 s):
```python
["ffprobe", "-v", "error", "-print_format", "json",
 "-show_format", "-show_streams", "-select_streams", "v:0", path]
```
   Non-zero exit / no video stream / unparsable JSON → 422 `CORRUPT_FILE`
   "We couldn't read this video, it may be corrupted. Try re-exporting it as MP4."
   Duration > `MAX_VIDEO_SECONDS` (+0.5 s tolerance) → 422 `DURATION_EXCEEDED`.
   Also reject absurd dimensions (> 4096 px) to bound decode cost.
5. Move to blob storage (`uploads/{video_id}/source.<ext>`), insert video + job, return 202.
6. `finally:` delete temp dir (`tempfile.TemporaryDirectory()` context manager).

A file with valid headers but broken frames can pass ffprobe; the worker catches decode failure
(ffmpeg non-zero exit or zero frames) → job `failed` with `DECODE_ERROR`. That's still a clean
failure for acceptance #2, make sure the UI shows the message.

## Fixtures for tests
- `tests/fixtures/corrupt.mp4`: `head -c 4096 /dev/urandom > corrupt.mp4` (commit; tiny).
- `tests/fixtures/fake.mp4`: a text file renamed → UNSUPPORTED_FORMAT.
- `tests/fixtures/tiny.mp4`: generate in CI: `ffmpeg -f lavfi -i testsrc=size=320x240:rate=10 -t 2
  -pix_fmt yuv420p tiny.mp4` (argument list in a conftest fixture), valid clip.
- Truncated: first 30 % of tiny.mp4 → CORRUPT_FILE or DECODE_ERROR.

## Tests
Unit: sniff function table-driven. Integration: POST each fixture → expected status + code; assert
temp dir empty afterwards; oversize simulated with a small `MAX_UPLOAD_MB` in test Settings.
