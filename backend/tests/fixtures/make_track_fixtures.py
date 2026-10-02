"""Regenerates the tracker fixtures (tracks_*.json) used by tests/unit/test_tracking.py.

Run from anywhere: python backend/tests/fixtures/make_track_fixtures.py
Each fixture is {"frames": [[{"box": [x1, y1, x2, y2], "score": s, "cls": "player"}, ...], ...]},
written one frame per line so a diff shows exactly which frame changed.
"""

import json
from pathlib import Path

# ---- config ----
OUT_DIR = Path(__file__).parent
BOX_W, BOX_H = 40, 100  # a standing player at broadcast distance
STEP_PX = 5  # per-frame movement of a walking player
MAX_AGE = 5  # must match TEST_PARAMS.max_age in test_tracking.py
# ----------------


def det(x: float, y: float, score: float = 0.9) -> dict:
    return {"box": [x, y, x + BOX_W, y + BOX_H], "score": score, "cls": "player"}


def single_moving() -> list[list[dict]]:
    return [[det(100 + STEP_PX * i, 200)] for i in range(20)]


def occlusion() -> list[list[dict]]:
    # Walking player, absent for frames 8-10 (3 frames < MAX_AGE).
    return [[] if 8 <= i <= 10 else [det(100 + STEP_PX * i, 200)] for i in range(20)]


def long_gap() -> list[list[dict]]:
    # Standing player, absent for MAX_AGE + 1 frames: the track must be dropped even though
    # the box reappears exactly where it was.
    gap = range(6, 6 + MAX_AGE + 1)
    return [[] if i in gap else [det(300, 200)] for i in range(6 + MAX_AGE + 1 + 6)]


def low_confidence() -> list[list[dict]]:
    # Partly hidden player: score drops to 0.3 (between low and high thresholds) for 5 frames.
    return [[det(100 + STEP_PX * i, 200, 0.3 if 6 <= i <= 10 else 0.9)] for i in range(18)]


def crossing() -> list[list[dict]]:
    # Two players on nearly the same line walking towards and past each other: at frame ~9
    # their boxes almost coincide; only the velocity prediction tells them apart.
    step = 10
    return [[det(100 + step * i, 200), det(280 - step * i, 210)] for i in range(20)]


def false_positive() -> list[list[dict]]:
    # A real player throughout, plus a one-frame box elsewhere at frame 5.
    frames = [[det(100, 200)] for _ in range(10)]
    frames[5].append(det(600, 300, 0.95))
    return frames


def staggered() -> list[list[dict]]:
    # Three players entering at frames 0, 5 and 10.
    starts = {0: 100, 5: 400, 10: 700}
    return [[det(x, 200) for start, x in starts.items() if i >= start] for i in range(16)]


FIXTURES = {
    "tracks_single_moving.json": single_moving,
    "tracks_occlusion.json": occlusion,
    "tracks_long_gap.json": long_gap,
    "tracks_low_confidence.json": low_confidence,
    "tracks_crossing.json": crossing,
    "tracks_false_positive.json": false_positive,
    "tracks_staggered.json": staggered,
}


def write(path: Path, frames: list[list[dict]]) -> None:
    lines = ",\n".join("  " + json.dumps(f) for f in frames)
    path.write_text('{"frames": [\n' + lines + "\n]}\n", encoding="utf-8")


if __name__ == "__main__":
    for name, make in FIXTURES.items():
        write(OUT_DIR / name, make())
        print("wrote", name)
