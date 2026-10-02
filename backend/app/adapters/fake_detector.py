"""Detector stand-in for tests and model-free pipeline runs: scripted detections per call."""

import numpy as np

from ..core.models import Detection


class FakeDetector:
    """Returns `by_frame[i]` on the i-th call (0-based), `default` for frames not listed."""

    def __init__(
        self,
        by_frame: dict[int, list[Detection]] | None = None,
        default: list[Detection] | None = None,
    ):
        self.by_frame = by_frame or {}
        self.default = default or []
        self.calls = 0

    def detect(self, frame_bgr: np.ndarray) -> list[Detection]:
        dets = self.by_frame.get(self.calls, self.default)
        self.calls += 1
        return list(dets)
