---
name: ffmpeg-frame-streaming
description: Streams video frames through ffmpeg subprocess pipes without loading the whole video into memory, ffprobe metadata, sampled decode at a configurable FPS to raw BGR frames, annotated re-encode to browser-playable H.264 MP4, rotation handling, deadlock-free pipes and error mapping. Use for decoding, frame sampling, drawing and encoding in the worker.
---

# Streaming frames with ffmpeg pipes

## Probe first
```python
cmd = ["ffprobe", "-v", "error", "-print_format", "json", "-show_format",
       "-show_streams", "-select_streams", "v:0", path]
```
Read `width`, `height`, `format.duration` (fallback stream duration), rotation (stream
`side_data_list[].rotation` or `tags.rotate`). ffmpeg auto-rotates on decode, so if rotation is
±90 swap width/height when computing the output frame size.

Output size: keep aspect, cap long side at `MAX_FRAME_SIDE` (default 1280), force even numbers.
Compute `W,H` yourself and pass explicit `scale=W:H` so the byte size per frame is known.

## Decoder (sampled at SAMPLE_FPS)
```python
dec_cmd = ["ffmpeg", "-v", "error", "-nostdin", "-i", src_path,
           "-t", str(settings.max_video_seconds),
           "-vf", f"fps={settings.sample_fps},scale={W}:{H}",
           "-f", "rawvideo", "-pix_fmt", "bgr24", "pipe:1"]
dec = subprocess.Popen(dec_cmd, stdout=subprocess.PIPE, stderr=err_file, shell=False)
frame_bytes = W * H * 3
while True:
    buf = read_exact(dec.stdout, frame_bytes)   # loop on .read until n bytes or EOF
    if buf is None: break                        # clean EOF (partial tail frame is dropped)
    frame = np.frombuffer(buf, np.uint8).reshape(H, W, 3)  # read-only view; copy before drawing
    yield frame
rc = dec.wait(timeout=30)
```
- Write stderr to a temp file (not `PIPE`), an unread stderr pipe can fill and deadlock.
- `rc != 0` or zero frames yielded → `DecodeError` → job `DECODE_ERROR` with a friendly message.
- Always `kill()` + `wait()` both processes in `finally` (no zombies when detection throws).
- Memory: one frame (~2.7 MB at 1280×720) + detector tensors. Never collect frames in a list.

## Encoder (annotated output)
```python
enc_cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24",
           "-s", f"{W}x{H}", "-r", str(settings.sample_fps), "-i", "pipe:0",
           "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", out_path]
enc = subprocess.Popen(enc_cmd, stdin=subprocess.PIPE, stderr=err_file2, shell=False)
enc.stdin.write(annotated.tobytes()) ...; enc.stdin.close(); enc.wait(timeout=120)
```
- `yuv420p` + `+faststart` = plays in every browser and starts before fully downloaded.
- Output runs at SAMPLE_FPS (e.g. 5 fps), choppy but honest: each frame shows real detections.
  "More time" idea: decode at native fps, run detection every k-th frame, interpolate boxes.

## Drawing (adapter, OpenCV)
`cv2.rectangle` + `cv2.putText(f"#{track_id}")` coloured by team; ball as a circle; small HUD
with frame time. Copy the frame first (`frame.copy()`): `np.frombuffer` arrays are read-only.

## Progress
`expected = ceil(min(duration, MAX_VIDEO_SECONDS) * SAMPLE_FPS)`;
report `min(99, int(done / expected * 100))` every `PROGRESS_EVERY_N_FRAMES` frames together with
the lease heartbeat.

## Tests
- Integration (needs ffmpeg, runs in CI): generate `testsrc` 2 s clip, stream at fps=5 → exactly
  10 frames of expected shape; encoder produces a file ffprobe can read.
- Unit: `read_exact` with a BytesIO returning short reads; output-size calculation (odd sizes,
  rotation, portrait).
