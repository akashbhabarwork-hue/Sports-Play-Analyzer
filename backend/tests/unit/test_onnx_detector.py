from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from app.adapters.fake_detector import FakeDetector
from app.adapters.onnx_detector import PAD_VALUE, OnnxYoloxDetector, letterbox
from app.config import MODEL_PATH
from app.core.models import Box, Detection, DetectorParams
from app.errors import ModelError

PARAMS = DetectorParams(input_size=640, player_min_score=0.1, ball_min_score=0.15, nms_iou=0.45)
PEOPLE_JPG = Path(__file__).resolve().parents[1] / "fixtures" / "people.jpg"


# ---- letterbox (OpenCV, no model) ----


def test_letterbox_landscape_fills_width_and_pads_bottom():
    frame = np.full((360, 1280, 3), 200, np.uint8)
    tensor, ratio = letterbox(frame, 640)

    assert tensor.shape == (1, 3, 640, 640) and tensor.dtype == np.float32
    assert ratio == pytest.approx(0.5)
    assert tensor[0, :, 179, 639].tolist() == [200, 200, 200]  # last image row
    assert tensor[0, :, 180, 0].tolist() == [PAD_VALUE] * 3  # first padded row


def test_letterbox_keeps_bgr_channel_order_and_raw_values():
    frame = np.zeros((64, 64, 3), np.uint8)
    frame[..., 0] = 10  # B
    frame[..., 2] = 250  # R
    tensor, _ = letterbox(frame, 64)
    assert tensor[0, 0, 0, 0] == 10 and tensor[0, 2, 0, 0] == 250  # no RGB swap, no /255


# ---- loading and export checks ----


def test_missing_model_raises_model_error_without_leaking_path(tmp_path):
    with pytest.raises(ModelError) as e:
        OnnxYoloxDetector(str(tmp_path / "nope.onnx"), PARAMS)
    assert e.value.code == "MODEL_ERROR"
    assert "nope.onnx" not in str(e.value)  # user-facing; the path is only logged


def test_unloadable_model_raises_model_error(tmp_path):
    bad = tmp_path / "bad.onnx"
    bad.write_bytes(b"not an onnx file")
    with pytest.raises(ModelError):
        OnnxYoloxDetector(str(bad), PARAMS)


def stub_detector(in_shape, out_shape) -> OnnxYoloxDetector:
    det = object.__new__(OnnxYoloxDetector)
    io = SimpleNamespace
    det.session = SimpleNamespace(
        get_inputs=lambda: [io(name="images", shape=in_shape)],
        get_outputs=lambda: [io(name="output", shape=out_shape)],
    )
    det.params = PARAMS
    return det


def test_check_io_accepts_raw_yolox_head():
    assert stub_detector([1, 3, 640, 640], [1, 8400, 85])._check_io() == "images"


def test_check_io_rejects_decoded_export():
    # e.g. an export with NMS baked in: (1, 100, 6)
    with pytest.raises(ModelError):
        stub_detector([1, 3, 640, 640], [1, 100, 6])._check_io()


def test_check_io_rejects_input_size_mismatch():
    with pytest.raises(ModelError):
        stub_detector([1, 3, 416, 416], [1, 3549, 85])._check_io()


# ---- fake ----


def test_fake_detector_scripts_detections_per_call():
    player = Detection(Box(0, 0, 10, 20), 0.9, "player")
    fake = FakeDetector({1: [player]})
    frame = np.zeros((4, 4, 3), np.uint8)

    assert fake.detect(frame) == []
    assert fake.detect(frame) == [player]
    assert fake.detect(frame) == []
    assert fake.calls == 3


# ---- real model (marker `model`; needs the weights at MODEL_PATH) ----


@pytest.mark.model
def test_real_model_finds_people_in_sample_frame():
    if not Path(MODEL_PATH).is_file():
        pytest.skip(f"model weights not at {MODEL_PATH}")
    detector = OnnxYoloxDetector(MODEL_PATH, PARAMS)
    frame = cv2.imread(str(PEOPLE_JPG))

    dets = detector.detect(frame)

    confident = [d for d in dets if d.cls == "player" and d.score >= 0.5]
    assert len(confident) >= 3
    h, w = frame.shape[:2]
    assert all(0 <= d.box.x1 < d.box.x2 <= w and 0 <= d.box.y1 < d.box.y2 <= h for d in dets)
