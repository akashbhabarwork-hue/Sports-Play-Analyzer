"""Draws the annotated video frames with OpenCV (boxes, player ids, ball, time, legend).

Since T-087 the video is drawn in a second pass, after the team split, so boxes are coloured
by team. The legend lists only what is actually drawn (no "Team B" entry if nobody is B).
"""

from collections.abc import Mapping, Sequence

import cv2
import numpy as np

from ..core.models import Box, Track

# The UI brief's colours, in OpenCV's BGR order: Team A #2563EB, Team B #E11D48.
TEAM_BGR: dict[str, tuple[int, int, int]] = {
    "A": (0xEB, 0x63, 0x25),
    "B": (0x48, 0x1D, 0xE1),
    "unknown": (160, 160, 160),
}
LEGEND_LABELS = {"A": "Team A", "B": "Team B", "unknown": "No team"}
BALL_BGR = (0, 215, 255)  # amber: visible on grass, wood and both kits
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
FONT = cv2.FONT_HERSHEY_SIMPLEX
THUMBNAIL_QUALITY = 80


def _pt(x: float, y: float) -> tuple[int, int]:
    return int(round(x)), int(round(y))


class OpenCvFrameAnnotator:
    def thumbnail_jpeg(self, frame_bgr: np.ndarray, max_width: int) -> bytes:
        height, width = frame_bgr.shape[:2]
        if width > max_width:
            size = (max_width, max(1, round(height * max_width / width)))
            frame_bgr = cv2.resize(frame_bgr, size, interpolation=cv2.INTER_AREA)
        ok, buf = cv2.imencode(".jpg", frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, THUMBNAIL_QUALITY])
        if not ok:
            raise ValueError("could not encode thumbnail")
        return buf.tobytes()

    def draw(
        self,
        frame_bgr: np.ndarray,
        tracks: Sequence[Track],
        ball: Box | None,
        t_s: float,
        teams: Mapping[int, str],
    ) -> np.ndarray:
        out = np.array(frame_bgr, copy=True)  # decoded frames are read-only views
        scale = max(out.shape[0] / 720, 0.4)  # keep text readable on small and large frames
        thick = max(1, int(round(2 * scale)))
        for track in tracks:
            if track.public_id is None:
                continue
            team = teams.get(track.public_id, "unknown")
            colour = TEAM_BGR.get(team, TEAM_BGR["unknown"])
            b = track.box
            cv2.rectangle(out, _pt(b.x1, b.y1), _pt(b.x2, b.y2), colour, thick)
            label = f"#{track.public_id}"
            (tw, th), _ = cv2.getTextSize(label, FONT, 0.6 * scale, thick)
            top = max(int(b.y1) - th - 6, 0)
            cv2.rectangle(out, (int(b.x1), top), (int(b.x1) + tw + 6, top + th + 6), colour, -1)
            text = BLACK if team == "unknown" else WHITE
            cv2.putText(out, label, (int(b.x1) + 3, top + th + 2), FONT, 0.6 * scale, text,
                        thick, cv2.LINE_AA)  # fmt: skip
        if ball is not None:
            centre = _pt((ball.x1 + ball.x2) / 2, (ball.y1 + ball.y2) / 2)
            radius = max(int((ball.x2 - ball.x1) / 2) + 3, 6)
            cv2.circle(out, centre, radius, BALL_BGR, thick)
        # Bottom-left: id labels sit above boxes, so a top-left time stamp could hide one.
        cv2.putText(out, f"{t_s:5.1f} s", (8, out.shape[0] - int(10 * scale) - 4), FONT,
                    0.7 * scale, WHITE, thick, cv2.LINE_AA)  # fmt: skip
        self._legend(out, sorted(set(teams.values())), scale)
        return out

    def _legend(self, out: np.ndarray, present: list[str], scale: float) -> None:
        """Top-right key: one swatch per team actually present, plus the ball."""
        items = [(LEGEND_LABELS.get(t, t), TEAM_BGR.get(t, TEAM_BGR["unknown"])) for t in present]
        items.append(("Ball", BALL_BGR))
        size = 0.45 * scale
        line = int(20 * scale) + 4
        width = max(cv2.getTextSize(text, FONT, size, 1)[0][0] for text, _ in items) + line + 12
        x0 = out.shape[1] - width - 6
        for i, (text, colour) in enumerate(items):
            y = 6 + i * line
            cv2.rectangle(out, (x0, y), (x0 + line - 6, y + line - 6), colour, -1)
            cv2.putText(out, text, (x0 + line, y + line - 8), FONT, size, WHITE, 1, cv2.LINE_AA)
