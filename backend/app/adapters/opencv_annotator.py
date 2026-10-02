"""Draws the annotated video frames with OpenCV (boxes, player ids, ball, time stamp).

Boxes are coloured by player id, not team: teams are only decided after the whole clip has
been seen (core/teams.py), and frames are encoded as they are drawn (D-026).
"""

from collections.abc import Sequence

import cv2
import numpy as np

from ..core.models import Box, Track

# Distinct BGR colours, readable on grass and on wooden courts.
PALETTE = (
    (255, 128, 0), (0, 200, 255), (255, 0, 255), (0, 255, 128), (255, 255, 0),
    (128, 0, 255), (0, 128, 255), (255, 0, 128), (128, 255, 0), (0, 255, 255),
)  # fmt: skip
BALL_COLOUR = (0, 0, 255)
TEXT_COLOUR = (255, 255, 255)
FONT = cv2.FONT_HERSHEY_SIMPLEX


def _pt(x: float, y: float) -> tuple[int, int]:
    return int(round(x)), int(round(y))


class OpenCvFrameAnnotator:
    def draw(
        self, frame_bgr: np.ndarray, tracks: Sequence[Track], ball: Box | None, t_s: float
    ) -> np.ndarray:
        out = np.array(frame_bgr, copy=True)  # decoded frames are read-only views
        scale = max(out.shape[0] / 720, 0.4)  # keep text readable on small and large frames
        thick = max(1, int(round(2 * scale)))
        for track in tracks:
            if track.public_id is None:
                continue
            colour = PALETTE[track.public_id % len(PALETTE)]
            b = track.box
            cv2.rectangle(out, _pt(b.x1, b.y1), _pt(b.x2, b.y2), colour, thick)
            label = f"#{track.public_id}"
            (tw, th), _ = cv2.getTextSize(label, FONT, 0.6 * scale, thick)
            top = max(int(b.y1) - th - 6, 0)
            cv2.rectangle(out, (int(b.x1), top), (int(b.x1) + tw + 6, top + th + 6), colour, -1)
            cv2.putText(out, label, (int(b.x1) + 3, top + th + 2), FONT, 0.6 * scale, (0, 0, 0),
                        thick, cv2.LINE_AA)  # fmt: skip
        if ball is not None:
            centre = _pt((ball.x1 + ball.x2) / 2, (ball.y1 + ball.y2) / 2)
            radius = max(int((ball.x2 - ball.x1) / 2) + 3, 6)
            cv2.circle(out, centre, radius, BALL_COLOUR, thick)
        cv2.putText(out, f"{t_s:5.1f} s", (8, int(24 * scale) + 4), FONT, 0.7 * scale,
                    TEXT_COLOUR, thick, cv2.LINE_AA)  # fmt: skip
        return out
