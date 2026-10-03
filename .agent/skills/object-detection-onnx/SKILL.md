---
name: object-detection-onnx
description: Runs a pretrained COCO object detector (default YOLOX-S ONNX, Apache-2.0; fallback Ultralytics YOLO, AGPL-3.0) with ONNX Runtime on CPU to detect players (person) and the ball (sports ball), model download with checksum, letterbox preprocessing, output decoding, NMS, thresholds from config and a FakeDetector for tests. Use for the detector adapter and model-choice ADR notes.
---

# Pretrained detection with ONNX Runtime

## Model choice (ADR talking points)
| Option | Licence | CPU speed @640 | Notes |
|---|---|---|---|
| **YOLOX-S ONNX** (default) | Apache-2.0 | ~5–10 fps on 1–2 vCPU (measure!) | No torch in image (small), permissive licence |
| YOLOX-Nano/Tiny | Apache-2.0 | faster | lower recall, ball worse |
| Ultralytics YOLO11n/YOLOv8n | **AGPL-3.0** | fast, easiest API | licence would force open-sourcing a networked service |
| Hosted vision API | paid | network-bound | cost per frame, data leaves infra |
COCO classes used: `0 person`, `32 sports ball`. No training (assignment rule). Accuracy caveat:
the ball is small and fast → recall is low; report ball-visible % honestly.

## Getting the model
- Download in the Dockerfile from the official YOLOX GitHub release (verify the exact release URL
  on the Megvii-BaseDetection/YOLOX releases page, don't trust a remembered URL), check sha256,
  store at `/models/yolox_s.onnx`. Env: `MODEL_PATH`, `MODEL_SHA256`.
- Don't commit weights to git.

## Preprocess (YOLOX convention - confirm against the repo's ONNXRuntime demo)
```python
def letterbox(img_bgr, size):               # returns padded CHW float32 + ratio
    r = min(size / img_bgr.shape[0], size / img_bgr.shape[1])
    resized = cv2.resize(img_bgr, (int(img_bgr.shape[1]*r), int(img_bgr.shape[0]*r)),
                         interpolation=cv2.INTER_LINEAR)
    padded = np.full((size, size, 3), 114, np.uint8)
    padded[:resized.shape[0], :resized.shape[1]] = resized
    return padded.transpose(2, 0, 1)[None].astype(np.float32), r   # BGR, 0–255, no mean/std
```
## Decode (exported YOLOX ONNX outputs raw grid predictions: (1, N, 85))
```python
def yolox_decode(out, size, strides=(8, 16, 32)):
    grids, exp_strides = [], []
    for s in strides:
        h = w = size // s
        xv, yv = np.meshgrid(np.arange(w), np.arange(h))
        grids.append(np.stack((xv, yv), 2).reshape(1, -1, 2))
        exp_strides.append(np.full((1, h * w, 1), s))
    grids = np.concatenate(grids, 1); exp_strides = np.concatenate(exp_strides, 1)
    out[..., :2] = (out[..., :2] + grids) * exp_strides
    out[..., 2:4] = np.exp(out[..., 2:4]) * exp_strides
    return out
```
Then: `boxes_cxcywh = out[0,:,:4]`, `scores = out[0,:,4:5] * out[0,:,5:]`; convert to xyxy,
divide by ratio `r`; keep classes {person, ball}; per-class NMS (`cv2.dnn.NMSBoxes` or a small
numpy NMS in core, pure, testable). Thresholds: `DETECT_CONF` for persons, `BALL_CONF` (lower,
e.g. 0.15) for ball, `DETECT_IOU_NMS` (0.45). Keep at most 1 ball (highest score) per frame.
At startup assert the model output shape matches `(1, N, 85)`; otherwise fail loudly with
`MODEL_ERROR` (this catches "exported with decode_in_inference" variants).

## Session options
`ort.InferenceSession(path, providers=["CPUExecutionProvider"], sess_options=so)` with
`so.intra_op_num_threads = settings.ort_threads` (match the machine's vCPUs). Build once per worker
process in `build_container`.

## Protocol + fake
```python
class Detector(Protocol):
    def detect(self, frame_bgr: np.ndarray) -> list[Detection]: ...
```
`FakeDetector(fixtures: dict[int, list[Detection]])` returns fixture detections per frame index,
used by unit/integration tests and the CI pipeline test (no model download in CI unit job).

## Tests
- Pure: NMS on overlapping boxes, xyxy conversion, ratio rescale, class filtering, single-ball rule.
- Decode: synthetic output tensor with one known cell → expected box.
- Optional smoke (marked `@pytest.mark.model`, skipped in unit CI): real model on a sample frame
  returns ≥1 person.
