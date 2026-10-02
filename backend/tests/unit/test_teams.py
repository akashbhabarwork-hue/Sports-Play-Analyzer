"""Team split by jersey colour on synthetic frames. No model, no video."""

import colorsys
import random
from uuid import UUID

import numpy as np
import pytest

from app.config import Settings, validate_settings
from app.core.metrics import build_stats
from app.core.models import Box, FrameObservation, MetricsParams, Track
from app.core.teams import (
    assign_teams,
    colour_feature,
    kmeans_two,
    rgb_to_hsv,
    torso_pixels,
    torso_region,
)

MIN_SEP = 0.2
RED, BLUE, WHITE, BLACK, GREEN = (
    (200, 30, 30),
    (30, 40, 200),
    (240, 240, 240),
    (20, 20, 20),
    (40, 140, 40),
)


def frame_with_players(colours: dict[int, tuple[int, int, int]], noise: int = 0, seed: int = 0):
    """Grass-green frame with one 40×100 player per id, shirt in the given colour.
    Returns (frame, {id: box})."""
    rng = np.random.default_rng(seed)
    frame = np.zeros((360, 640, 3), dtype=np.uint8)
    frame[:] = GREEN
    boxes = {}
    for i, (pid, colour) in enumerate(sorted(colours.items())):
        x, y = 20 + 60 * i, 100
        frame[y : y + 100, x : x + 40] = (60, 60, 60)  # shorts/legs/head
        frame[y + 15 : y + 55, x : x + 40] = colour  # shirt covers the torso band
        boxes[pid] = Box(x, y, x + 40, y + 100)
    if noise:
        jitter = rng.integers(-noise, noise + 1, frame.shape)
        frame = np.clip(frame.astype(int) + jitter, 0, 255).astype(np.uint8)
    return frame, boxes


def features(colours, noise=0, seed=0, samples=3):
    """Per-player feature samples from `samples` independently-noised frames."""
    out: dict[int, list[np.ndarray]] = {pid: [] for pid in colours}
    for k in range(samples):
        frame, boxes = frame_with_players(colours, noise, seed + k)
        for pid, box in boxes.items():
            out[pid].append(colour_feature(torso_pixels(frame, box)))
    return out


def test_team_split_two_colours():
    colours = {1: RED, 2: BLUE, 3: RED, 4: BLUE, 5: RED, 6: BLUE}
    teams = assign_teams(features(colours, noise=15), MIN_SEP)
    assert teams == {1: "A", 2: "B", 3: "A", 4: "B", 5: "A", 6: "B"}


def test_team_identical_colours_are_unknown():
    colours = {pid: RED for pid in range(1, 7)}
    assert set(assign_teams(features(colours, noise=10), MIN_SEP).values()) == {"unknown"}


def test_team_white_vs_black_kits_split():
    # Both have ~zero saturation: only the value channel separates them.
    colours = {1: WHITE, 2: BLACK, 3: WHITE, 4: BLACK}
    assert assign_teams(features(colours), MIN_SEP) == {1: "A", 2: "B", 3: "A", 4: "B"}


def test_team_red_hue_wraps_around():
    # Hue ~359° and ~1° are both red; raw hue would put them at opposite ends.
    red_low = tuple(int(255 * c) for c in colorsys.hsv_to_rgb(0.003, 0.85, 0.8))
    red_high = tuple(int(255 * c) for c in colorsys.hsv_to_rgb(0.997, 0.85, 0.8))
    colours = {1: red_low, 2: BLUE, 3: red_high, 4: BLUE, 5: red_low}
    teams = assign_teams(features(colours), MIN_SEP)
    assert teams[1] == teams[3] == teams[5] == "A"
    assert teams[2] == teams[4] == "B"


def test_team_labels_are_deterministic_and_order_independent():
    colours = {3: BLUE, 7: RED, 1: BLUE, 9: RED}
    feats = features(colours, noise=20, seed=5)
    first = assign_teams(feats, MIN_SEP)
    shuffled = dict(random.Random(1).sample(list(feats.items()), len(feats)))
    assert assign_teams(shuffled, MIN_SEP) == first
    assert first[1] == "A"  # lowest id names team A
    assert first == {1: "A", 3: "A", 7: "B", 9: "B"}


def test_team_too_few_players_are_unknown():
    assert assign_teams({}, MIN_SEP) == {}
    assert assign_teams(features({4: RED}), MIN_SEP) == {4: "unknown"}
    # A track with no usable crops is unknown; the others are still split.
    feats = features({1: RED, 2: BLUE, 3: RED})
    feats[5] = []
    assert assign_teams(feats, MIN_SEP) == {1: "A", 2: "B", 3: "A", 5: "unknown"}


def test_team_min_separation_threshold():
    feats = {1: [np.array([0.0, 0.0, 0.5])], 2: [np.array([0.0, 0.0, 0.6])]}
    assert set(assign_teams(feats, 0.2).values()) == {"unknown"}
    assert assign_teams(feats, 0.05) == {1: "A", 2: "B"}


def test_team_track_feature_is_median_of_samples():
    # One bad sample (a crop that caught the referee) doesn't flip the track.
    red, blue = colour_feature(np.array([RED])), colour_feature(np.array([BLUE]))
    feats = {1: [red, red, blue], 2: [blue, blue], 3: [red]}
    assert assign_teams(feats, MIN_SEP) == {1: "A", 2: "B", 3: "A"}


def test_kmeans_two_separates_blobs():
    rng = np.random.default_rng(0)
    pts = np.vstack([rng.normal(0, 0.05, (10, 3)), rng.normal(1, 0.05, (10, 3))])
    labels, centres = kmeans_two(pts)
    assert len(set(labels[:10])) == 1 and len(set(labels[10:])) == 1
    assert labels[0] != labels[10]
    assert np.linalg.norm(centres[0] - centres[1]) == pytest.approx(np.sqrt(3), abs=0.1)


def test_team_torso_region_and_crop():
    assert torso_region(Box(100, 200, 140, 300)) == Box(112, 220, 128, 250)
    frame = np.zeros((50, 50, 3), dtype=np.uint8)
    assert torso_pixels(frame, Box(10, 10, 20, 40)).shape == (4 * 9, 3)
    # Box partly outside the frame: crop is clamped, fully outside -> None.
    assert torso_pixels(frame, Box(30, 10, 70, 40)).shape == (8 * 9, 3)  # torso x 42..58 -> 42..50
    assert torso_pixels(frame, Box(100, 100, 140, 200)) is None


def test_team_rgb_to_hsv_matches_colorsys():
    rng = np.random.default_rng(1)
    rgb = rng.integers(0, 256, (200, 3)).astype(np.uint8)
    rgb[:3] = [[0, 0, 0], [255, 255, 255], [128, 128, 128]]  # greys: no hue
    ours = rgb_to_hsv(rgb)
    ref = np.array([colorsys.rgb_to_hsv(*(c / 255 for c in px)) for px in rgb.astype(float)])
    assert np.allclose(ours, ref, atol=1e-9)


def test_team_heatmap_is_sum_of_members():
    def player(pid, x):
        box = Box(x - 20, 300, x + 20, 400)
        return Track(pid, pid, box, 0.0, 0.0, hits=3, misses=0, state="confirmed")

    frames = [
        FrameObservation(i, i / 5, (player(1, 100 + 5 * i), player(2, 600), player(3, 1100)))
        for i in range(8)
    ]
    params = MetricsParams(2.0, 5, 8, 4, 0.5, 3)
    teams = {1: "A", 2: "B", 3: "A"}
    result = build_stats(UUID(int=1), frames, 1280, 720, params, teams=teams)
    rows = {r.track_id: r.heatmap["counts"] for r in result.tracks}
    team_a = result.stats["heatmaps"]["A"]["counts"]
    assert team_a == [a + b for a, b in zip(rows[1], rows[3])]
    assert result.stats["heatmaps"]["B"]["counts"] == rows[2]
    assert result.stats["teams"]["A"]["players"] == [1, 3]
    assert [p["team"] for p in result.stats["players"]] == ["A", "B", "A"]


def test_team_min_separation_setting_validated():
    s = Settings(app_env="dev", app_origin="http://x", database_url="", git_sha="")
    assert s.team_min_separation == 0.2
    bad = Settings(
        app_env="dev", app_origin="http://x", database_url="", git_sha="", team_min_separation=-1
    )
    with pytest.raises(RuntimeError, match="TEAM_MIN_SEPARATION"):
        validate_settings(bad)


def test_team_crop_feature_ignores_minority_pixels():
    # 40 % of the shirt crop is a white number/stripe: the median still reads the shirt colour.
    shirt = np.array([RED] * 60 + [WHITE] * 40, dtype=np.uint8)
    assert colour_feature(shirt) == pytest.approx(colour_feature(np.array([RED], dtype=np.uint8)))


def test_team_one_garbage_sample_does_not_isolate_a_player():
    red, blue = colour_feature(np.array([RED])), colour_feature(np.array([BLUE]))
    garbage = np.array([-10.0, -10.0, 0.0])  # a crop that caught nothing like a shirt
    feats = {1: [red, red, garbage], 2: [blue], 3: [red], 4: [blue]}
    assert assign_teams(feats, MIN_SEP) == {1: "A", 2: "B", 3: "A", 4: "B"}
