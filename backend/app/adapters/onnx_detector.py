"""Pretrained YOLOX-S via ONNX Runtime on CPU (Apache-2.0, D-025). Built once per worker.

This adapter only does I/O-shaped work: load the model, letterbox the frame (OpenCV resize),
run inference. Decoding, NMS and the player/ball rules are pure, in core/detection.py.
"""

import logging
import os

import cv2
import numpy as np
import onnxruntime as ort

from ..core.detection import decode_yolox, letterbox_ratio, select_detections, yolox_num_anchors
from ..core.models import Detection, DetectorParams
from ..errors import ModelError

logger = logging.getLogger(__name__)

PAD_VALUE = 114  # YOLOX training pad colour
MODEL_MESSAGE = "The player detector failed. Please try again later."


def letterbox(frame_bgr: np.ndarray, size: int) -> tuple[np.ndarray, float]:
    """Resize keeping aspect into a size×size grey canvas (top-left); NCHW float32 BGR 0..255.

    YOLOX (legacy=False, as released) takes raw BGR pixel values: no RGB swap, no mean/std.
    """
    height, width = frame_bgr.shape[:2]
    ratio = letterbox_ratio(height, width, size)
    new_w, new_h = min(size, int(width * ratio)), min(size, int(height * ratio))
    resized = cv2.resize(frame_bgr, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((size, size, 3), PAD_VALUE, np.uint8)
    canvas[:new_h, :new_w] = resized
    return canvas.transpose(2, 0, 1)[None].astype(np.float32), ratio


class OnnxYoloxDetector:
    def __init__(self, model_path: str, params: DetectorParams, threads: int = 0):
        # Details go to the logs; the message may reach users through jobs.error_message.
        if not os.path.isfile(model_path):
            logger.error("detector model file missing", extra={"model_path": model_path})
            raise ModelError(MODEL_MESSAGE)
        options = ort.SessionOptions()
        if threads:
            options.intra_op_num_threads = threads
        try:
            self.session = ort.InferenceSession(
                model_path, sess_options=options, providers=["CPUExecutionProvider"]
            )
        except Exception as e:  # onnxruntime raises its own pybind exception types
            logger.exception("detector model could not be loaded")
            raise ModelError(MODEL_MESSAGE) from e
        self.params = params
        self.input_name = self._check_io()

    def _check_io(self) -> str:
        """Fail at startup, not mid-job, if this is a different export (e.g. decoded outputs)."""
        size = self.params.input_size
        (inp,) = self.session.get_inputs()
        (out,) = self.session.get_outputs()
        expected_in, expected_out = [1, 3, size, size], [1, yolox_num_anchors(size), 85]
        if list(inp.shape) != expected_in or list(out.shape) != expected_out:
            logger.error(
                "detector model is not a raw YOLOX export for DETECT_INPUT_SIZE",
                extra={"input": str(inp.shape), "output": str(out.shape), "size": size},
            )
            raise ModelError(MODEL_MESSAGE)
        return inp.name

    def detect(self, frame_bgr: np.ndarray) -> list[Detection]:
        tensor, ratio = letterbox(frame_bgr, self.params.input_size)
        try:
            (raw,) = self.session.run(None, {self.input_name: tensor})
        except Exception as e:
            logger.exception("onnxruntime inference failed")
            raise ModelError(MODEL_MESSAGE) from e
        boxes, scores = decode_yolox(raw, self.params.input_size)
        return select_detections(boxes, scores, ratio, frame_bgr.shape[:2], self.params)
