"""Draws the annotated video frames with OpenCV in a broadcast "AI tracking" style.

Per player: a translucent team-coloured spotlight under the feet, corner brackets around the
body and an id badge. The ball gets a glow and a short fading trail. A HUD panel (top-left)
shows that the frame was analysed, how many players are tracked and the time; a legend
(top-right) lists only what is actually drawn. Since T-087 boxes are coloured by team.
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
ACCENT_BGR = (0xE5, 0x46, 0x4F)  # brand indigo #4F46E5
LIVE_BGR = (0x5E, 0xC5, 0x22)  # green "tracking" dot #22C55E
PANEL_BGR = (20, 16, 15)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
FONT = cv2.FONT_HERSHEY_SIMPLEX
THUMBNAIL_QUALITY = 80
FILL_ALPHA = 0.38  # spotlights, glow and panels
WATERMARK = "AI ANALYSIS  |  Sports Play Analyzer"
MAX_TRAIL_JUMP = 0.12  # of frame width, per sampled frame


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
        ball_trail: Sequence[tuple[float, float]] = (),
    ) -> np.ndarray:
        out = np.array(frame_bgr, copy=True)  # decoded frames are read-only views
        scale = max(out.shape[0] / 720, 0.4)  # keep text readable on small and large frames
        thick = max(1, int(round(2 * scale)))
        shown = [(t, teams.get(t.public_id, "unknown")) for t in tracks if t.public_id is not None]

        # 1) Translucent layer: everything drawn here is blended once, so untouched pixels stay.
        layer = out.copy()
        for track, team in shown:
            b = track.box
            w = b.x2 - b.x1
            axes = (max(int(w * 0.5), 4), max(int(w * 0.16), 2))
            colour = TEAM_BGR.get(team, TEAM_BGR["unknown"])
            cv2.ellipse(
                layer, _pt((b.x1 + b.x2) / 2, b.y2), axes, 0, 0, 360, colour, -1, cv2.LINE_AA
            )
        if ball is not None:
            centre, radius = _ball_geometry(ball)
            cv2.circle(layer, centre, radius * 2, BALL_BGR, -1, cv2.LINE_AA)
        hud_box = self._hud_box(out, scale)
        cv2.rectangle(layer, hud_box[0], hud_box[1], PANEL_BGR, -1)
        # The whole clip's teams, not this frame's: the key must not flicker as players come and go.
        legend = self._legend_items(sorted(set(teams.values())))
        legend_box = self._legend_box(out, legend, scale)
        cv2.rectangle(layer, legend_box[0], legend_box[1], PANEL_BGR, -1)
        mark_box = self._watermark_box(out, scale)
        cv2.rectangle(layer, mark_box[0], mark_box[1], PANEL_BGR, -1)
        out = cv2.addWeighted(layer, FILL_ALPHA, out, 1 - FILL_ALPHA, 0)

        # 2) Solid marks on top.
        self._trail(out, ball_trail, ball, thick)
        for track, team in shown:
            self._player(out, track, team, scale, thick)
        if ball is not None:
            centre, radius = _ball_geometry(ball)
            cv2.circle(out, centre, radius, BALL_BGR, thick, cv2.LINE_AA)
        self._hud(out, hud_box, len(shown), ball is not None, t_s, scale)
        self._legend(out, legend, legend_box, scale)
        self._watermark(out, mark_box, scale)
        return out

    def _player(self, out: np.ndarray, track: Track, team: str, scale: float, thick: int) -> None:
        colour = TEAM_BGR.get(team, TEAM_BGR["unknown"])
        b = track.box
        x1, y1, x2, y2 = int(b.x1), int(b.y1), int(b.x2), int(b.y2)
        arm = max(int(min(x2 - x1, y2 - y1) * 0.28), 3)
        for (cx, cy), (dx, dy) in (
            ((x1, y1), (1, 1)),
            ((x2, y1), (-1, 1)),
            ((x1, y2), (1, -1)),
            ((x2, y2), (-1, -1)),
        ):
            cv2.line(out, (cx, cy), (cx + dx * arm, cy), colour, thick)  # crisp, exact colour
            cv2.line(out, (cx, cy), (cx, cy + dy * arm), colour, thick)
        label = f"#{track.public_id}"
        size = 0.55 * scale
        (tw, th), _ = cv2.getTextSize(label, FONT, size, thick)
        pad = max(int(4 * scale), 2)
        left = (x1 + x2) // 2 - tw // 2 - pad
        bottom = y1 - max(int(4 * scale), 2)
        top = max(bottom - th - 2 * pad, 0)
        cv2.rectangle(out, (left, top), (left + tw + 2 * pad, top + th + 2 * pad), colour, -1)
        text = BLACK if team == "unknown" else WHITE
        cv2.putText(out, label, (left + pad, top + th + pad), FONT, size, text, thick, cv2.LINE_AA)

    def _trail(
        self,
        out: np.ndarray,
        trail: Sequence[tuple[float, float]],
        ball: Box | None,
        thick: int,
    ) -> None:
        """Fading line from older to newer ball positions, ending at the current ball.

        Drawn only while the ball is visible, and only the chain connected to it: walking back
        from the ball, the trail stops at the first jump longer than MAX_TRAIL_JUMP of the
        frame width (a far jump is a false detection, not the ball's path).
        """
        if ball is None:
            return
        points = [_pt(x, y) for x, y in trail]
        points.append(_ball_geometry(ball)[0])
        max_jump = MAX_TRAIL_JUMP * out.shape[1]
        first = len(points) - 1
        while first > 0:
            (ax, ay), (bx, by) = points[first - 1], points[first]
            if ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5 > max_jump:
                break
            first -= 1
        points = points[first:]
        for i in range(1, len(points)):
            fade = i / len(points)  # 0 → oldest, 1 → newest
            colour = tuple(int(c * (0.35 + 0.65 * fade)) for c in BALL_BGR)
            width = max(1, int(round(thick * (0.5 + fade))))
            cv2.line(out, points[i - 1], points[i], colour, width, cv2.LINE_AA)

    def _hud_box(self, out: np.ndarray, scale: float) -> tuple[tuple[int, int], tuple[int, int]]:
        line = int(22 * scale) + 4
        width = int(250 * scale) + 16
        return (6, 6), (min(6 + width, out.shape[1] - 1), 6 + 2 * line + 6)

    def _hud(
        self,
        out: np.ndarray,
        box: tuple[tuple[int, int], tuple[int, int]],
        players: int,
        ball_seen: bool,
        t_s: float,
        scale: float,
    ) -> None:
        (x0, y0), _ = box
        line = int(22 * scale) + 4
        size = 0.5 * scale
        dot = max(int(5 * scale), 2)
        cv2.circle(out, (x0 + 8 + dot, y0 + line // 2 + 3), dot, LIVE_BGR, -1, cv2.LINE_AA)
        cv2.putText(out, "AI TRACKING", (x0 + 14 + 2 * dot, y0 + line - 4), FONT, size, WHITE,
                    1, cv2.LINE_AA)  # fmt: skip
        noun = "player" if players == 1 else "players"
        detail = f"{players} {noun}  ball {'yes' if ball_seen else '--'}  {t_s:5.1f} s"
        cv2.putText(out, detail, (x0 + 8, y0 + 2 * line - 2), FONT, size * 0.9, WHITE, 1,
                    cv2.LINE_AA)  # fmt: skip
        cv2.line(out, (x0, y0), (x0, y0 + 2 * line + 6), ACCENT_BGR, max(2, int(3 * scale)))

    def _legend_items(self, present: list[str]) -> list[tuple[str, tuple[int, int, int]]]:
        items = [(LEGEND_LABELS.get(t, t), TEAM_BGR.get(t, TEAM_BGR["unknown"])) for t in present]
        items.append(("Ball", BALL_BGR))
        return items

    def _legend_box(
        self, out: np.ndarray, items: list[tuple[str, tuple[int, int, int]]], scale: float
    ) -> tuple[tuple[int, int], tuple[int, int]]:
        size = 0.45 * scale
        line = int(20 * scale) + 4
        width = max(cv2.getTextSize(text, FONT, size, 1)[0][0] for text, _ in items) + line + 16
        x0 = max(out.shape[1] - width - 6, 0)
        return (x0, 6), (out.shape[1] - 6, 6 + len(items) * line + 6)

    def _legend(
        self,
        out: np.ndarray,
        items: list[tuple[str, tuple[int, int, int]]],
        box: tuple[tuple[int, int], tuple[int, int]],
        scale: float,
    ) -> None:
        """Top-right key: one swatch per team actually present, plus the ball."""
        size = 0.45 * scale
        line = int(20 * scale) + 4
        (x0, y0), _ = box
        for i, (text, colour) in enumerate(items):
            y = y0 + 6 + i * line
            r = max((line - 8) // 2, 2)
            cv2.circle(out, (x0 + 6 + r, y + r + 1), r, colour, -1, cv2.LINE_AA)
            cv2.putText(out, text, (x0 + line + 6, y + line - 9), FONT, size, WHITE, 1,
                        cv2.LINE_AA)  # fmt: skip

    def _watermark_box(
        self, out: np.ndarray, scale: float
    ) -> tuple[tuple[int, int], tuple[int, int]]:
        (tw, th), _ = cv2.getTextSize(WATERMARK, FONT, 0.42 * scale, 1)
        bottom = out.shape[0] - 6
        return (6, bottom - th - 12), (min(6 + tw + 16, out.shape[1] - 1), bottom)

    def _watermark(
        self, out: np.ndarray, box: tuple[tuple[int, int], tuple[int, int]], scale: float
    ) -> None:
        """Bottom-left: a small "AI analysis" mark on its translucent panel (no shadow text)."""
        (x0, _), (_, y1) = box
        cv2.putText(out, WATERMARK, (x0 + 8, y1 - 6), FONT, 0.42 * scale, WHITE, 1, cv2.LINE_AA)


def _ball_geometry(ball: Box) -> tuple[tuple[int, int], int]:
    centre = _pt((ball.x1 + ball.x2) / 2, (ball.y1 + ball.y2) / 2)
    return centre, max(int((ball.x2 - ball.x1) / 2) + 3, 6)
