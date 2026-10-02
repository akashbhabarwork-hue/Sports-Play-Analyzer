"""Metric maths on hand-built observations: distance, heatmaps, ball %, possession, stats JSON."""

import json
import random
from dataclasses import replace
from uuid import UUID

import pytest

from app.config import Settings, validate_settings
from app.core.heatmap import build_heatmap, heatmap_cell, sum_heatmaps
from app.core.metrics import ball_visible_pct, build_stats, path_distance
from app.core.models import Box, FrameObservation, MetricsParams, Track
from app.core.possession import count_possession, possession_candidate, possession_owners
from app.wiring import metrics_params

JOB = UUID("00000000-0000-0000-0000-000000000001")
PARAMS = MetricsParams(
    jitter_px=2.0,
    max_gap_frames=5,
    heatmap_w=4,
    heatmap_h=2,
    possession_dist_ratio=0.5,
    possession_min_frames=3,
)


def player(pid: int, feet_x: float, feet_y: float, height: float = 100) -> Track:
    box = Box(feet_x - 20, feet_y - height, feet_x + 20, feet_y)
    return Track(pid, pid, box, 0.0, 0.0, hits=3, misses=0, state="confirmed")


def ball_at(x: float, y: float) -> Box:
    return Box(x - 5, y - 5, x + 5, y + 5)


def obs(i: int, *tracks: Track, ball: Box | None = None) -> FrameObservation:
    return FrameObservation(frame_idx=i, t_s=i / 5, tracks=tracks, ball=ball)


# ---- distance ----


def test_metric_distance_straight_line():
    samples = [(i, i / 5, 100.0 + 10 * i, 200.0) for i in range(11)]  # 10 steps of 10 px
    assert path_distance(samples, 2.0, 5) == pytest.approx(100.0)


def test_metric_distance_jitter_filtered():
    rng = random.Random(7)
    samples = [
        (i, i / 5, 100 + 10 * i + rng.uniform(-1, 1), 200 + rng.uniform(-1, 1)) for i in range(11)
    ]
    assert path_distance(samples, 2.0, 5) == pytest.approx(100.0, abs=4.0)


def test_metric_standing_player_wobble_counts_nothing():
    rng = random.Random(3)
    samples = [(i, i / 5, 300 + rng.uniform(-1, 1), 200 + rng.uniform(-1, 1)) for i in range(50)]
    assert path_distance(samples, 2.0, 5) == 0.0


def test_metric_slow_walker_still_accumulates():
    # 1 px per frame is below the 2 px jitter step, but measured from the last counted point
    # the walk is not lost.
    samples = [(i, i / 5, 100.0 + i, 200.0) for i in range(21)]
    assert path_distance(samples, 2.0, 5) == pytest.approx(20.0)


def test_metric_distance_gap_not_bridged():
    before = [(i, i / 5, 100.0 + 10 * i, 200.0) for i in range(5)]  # 40 px
    after = [(i, i / 5, 900.0 + 10 * (i - 20), 200.0) for i in range(20, 25)]  # 40 px
    assert path_distance(before + after, 2.0, 5) == pytest.approx(80.0)
    # A gap of exactly max_gap missing frames is still bridged.
    near = [(i, i / 5, 240.0 + 10 * (i - 10), 200.0) for i in range(10, 12)]  # +100 px
    assert path_distance(before + near, 2.0, 5) == pytest.approx(40.0 + 100.0 + 10.0)


def test_metric_distance_empty_and_single():
    assert path_distance([], 2.0, 5) == 0.0
    assert path_distance([(0, 0.0, 1.0, 1.0)], 2.0, 5) == 0.0


# ---- heatmap ----


@pytest.mark.parametrize(
    "nx, ny, cell",
    [
        (0.0, 0.0, (0, 0)),
        (1.0, 1.0, (3, 1)),  # right/bottom edge lands in the last cell, not out of range
        (0.999, 0.5, (3, 1)),
        (0.25, 0.49, (1, 0)),
        (-0.01, 1.2, (0, 1)),  # boxes cut by the frame border are clamped in
    ],
)
def test_heatmap_cell_edges(nx, ny, cell):
    assert heatmap_cell(nx, ny, 4, 2) == cell


def test_heatmap_counts_total_equals_observations():
    rng = random.Random(1)
    points = [(rng.random(), rng.random()) for _ in range(500)] + [(1.0, 1.0)] * 3
    hm = build_heatmap(points, 32, 18)
    assert len(hm["counts"]) == 32 * 18
    assert sum(hm["counts"]) == 503
    assert hm["max"] == max(hm["counts"])
    assert (hm["w"], hm["h"]) == (32, 18)


def test_heatmap_is_row_major():
    hm = build_heatmap([(0.9, 0.0), (0.0, 0.9)], 4, 2)
    assert hm["counts"] == [0, 0, 0, 1, 1, 0, 0, 0]


def test_heatmap_sum_and_empty():
    a = build_heatmap([(0.0, 0.0)], 4, 2)
    b = build_heatmap([(0.0, 0.0), (0.9, 0.9)], 4, 2)
    total = sum_heatmaps([a, b], 4, 2)
    assert total["counts"][0] == 2 and total["counts"][7] == 1 and total["max"] == 2
    assert sum_heatmaps([], 4, 2) == {"w": 4, "h": 2, "counts": [0] * 8, "max": 0}
    with pytest.raises(ValueError):
        sum_heatmaps([build_heatmap([], 2, 2)], 4, 2)


# ---- ball visible ----


def test_metric_ball_visible_three_of_twelve_is_25():
    frames = [obs(i, ball=ball_at(50, 50) if i in (2, 5, 9) else None) for i in range(12)]
    assert ball_visible_pct(frames) == 25.0
    assert ball_visible_pct([]) == 0.0


def test_metric_ball_visible_rounds_to_one_decimal():
    frames = [obs(i, ball=ball_at(1, 1) if i == 0 else None) for i in range(3)]
    assert ball_visible_pct(frames) == 33.3


# ---- possession ----


def test_possession_candidate_nearest_within_ratio():
    p1, p2 = player(1, 100, 300), player(2, 160, 300)
    assert possession_candidate(ball_at(110, 295), (p1, p2), 0.5) == 1
    assert possession_candidate(ball_at(150, 295), (p1, p2), 0.5) == 2
    # 60 px from the nearest feet with 100 px boxes: beyond 0.5 × height -> loose ball.
    assert possession_candidate(ball_at(100, 360), (p1, p2), 0.5) is None
    assert possession_candidate(ball_at(100, 300), (), 0.5) is None


def test_possession_hysteresis_brief_contact_never_owns():
    # Ball near P1 for 1 frame, then P2 for 5 (min_frames=3): P1 never owns it.
    p1, p2 = player(1, 100, 300), player(2, 500, 300)
    frames = [obs(0, p1, p2, ball=ball_at(100, 300))] + [
        obs(i, p1, p2, ball=ball_at(500, 300)) for i in range(1, 6)
    ]
    owners = possession_owners(frames, PARAMS)
    assert owners == [None, None, None, 2, 2, 2]
    assert 1 not in owners
    count = count_possession(frames, PARAMS)
    assert count.by_player == {2: 3} and count.unassigned == 3 and count.ball_frames == 6


def test_possession_owner_keeps_ball_through_short_pass():
    p1, p2 = player(1, 100, 300), player(2, 500, 300)
    near1 = [obs(i, p1, p2, ball=ball_at(100, 300)) for i in range(4)]
    loose = [obs(i, p1, p2, ball=ball_at(300, 100)) for i in range(4, 6)]  # 2 loose frames
    back1 = [obs(i, p1, p2, ball=ball_at(100, 300)) for i in range(6, 8)]
    assert possession_owners(near1 + loose + back1, PARAMS) == [None, None, 1, 1, 1, 1, 1, 1]


def test_possession_short_ball_gap_keeps_owner_long_gap_resets():
    p1 = player(1, 100, 300)
    own = [obs(i, p1, ball=ball_at(100, 300)) for i in range(3)]
    short_gap = [obs(i, p1) for i in range(3, 5)]  # 2 frames unseen
    after = [obs(5, p1, ball=ball_at(100, 300))]
    assert possession_owners(own + short_gap + after, PARAMS)[-1] == 1
    long_gap = [obs(i, p1) for i in range(3, 6)]  # 3 frames unseen
    after = [obs(6, p1, ball=ball_at(100, 300))]
    assert possession_owners(own + long_gap + after, PARAMS)[-1] is None


def test_possession_unseen_frames_not_in_percentages():
    p1 = player(1, 100, 300)
    frames = [obs(i, p1, ball=ball_at(100, 300)) for i in range(4)] + [obs(4, p1)]
    count = count_possession(frames, PARAMS)
    assert count.ball_frames == 4 and count.by_player == {1: 2} and count.unassigned == 2


def test_possession_min_frames_one_is_immediate():
    p1 = player(1, 100, 300)
    params = replace(PARAMS, possession_min_frames=1)
    assert possession_owners([obs(0, p1, ball=ball_at(100, 300))], params) == [1]


# ---- stats JSON ----


def match() -> list[FrameObservation]:
    """Two players, 10 frames at 1280×720: P1 walks right 10 px/frame with the ball,
    P2 stands still; the ball is hidden in the last 2 frames."""
    frames = []
    for i in range(10):
        p1 = player(1, 100 + 10 * i, 400)
        p2 = player(2, 900, 500)
        frames.append(obs(i, p1, p2, ball=ball_at(100 + 10 * i, 395) if i < 8 else None))
    return frames


def test_metric_stats_contract():
    result = build_stats(JOB, match(), 1280, 720, PARAMS, teams={1: "A", 2: "B"})
    s = result.stats
    assert s["job_id"] == str(JOB)
    assert s["players_tracked"] == 2
    assert s["ball_visible_pct"] == 80.0
    assert s["possession"]["by_player"] == [{"player_id": 1, "pct": 75.0}]
    assert s["possession"]["by_team"] == {"A": 75.0, "B": 0.0}
    assert s["possession"]["unassigned_pct"] == 25.0
    p1, p2 = s["players"]
    assert p1 == {
        "player_id": 1,
        "team": "A",
        "distance_px": 90.0,
        "distance_rel": round(90 / 1468.6, 3),
        "frames_visible": 10,
        "possession_pct": 75.0,
    }
    assert p2["distance_px"] == 0.0 and p2["possession_pct"] == 0.0
    assert s["teams"] == {
        "A": {"players": [1], "distance_rel_total": p1["distance_rel"]},
        "B": {"players": [2], "distance_rel_total": 0.0},
    }
    assert sum(s["heatmaps"]["all"]["counts"]) == 20
    json.dumps(s)  # must be JSON-serialisable as stored in jsonb


def test_metric_player_rows_match_stats():
    result = build_stats(JOB, match(), 1280, 720, PARAMS)
    r1 = result.tracks[0]
    assert (r1.job_id, r1.track_id, r1.team, r1.frames_visible) == (JOB, 1, "unknown", 10)
    assert r1.possession_frames == 6
    assert sum(r1.heatmap["counts"]) == 10
    assert r1.track[0] == [0.0, round(100 / 1280, 4), round(400 / 720, 4)]
    assert len(r1.track) == 10


def test_metric_team_heatmaps_are_sums_of_members():
    teams = {1: "A", 2: "A"}
    s = build_stats(JOB, match(), 1280, 720, PARAMS, teams=teams).stats
    assert s["heatmaps"]["A"] == s["heatmaps"]["all"]
    assert s["heatmaps"]["B"]["max"] == 0
    assert s["teams"]["A"]["players"] == [1, 2]


def test_metric_stats_empty_video():
    s = build_stats(JOB, [], 1280, 720, PARAMS).stats
    assert s["players_tracked"] == 0 and s["players"] == []
    assert s["ball_visible_pct"] == 0.0 and s["possession"]["unassigned_pct"] == 0.0


def test_metric_tentative_ids_ignored():
    t = replace(player(1, 100, 300), public_id=None, state="tentative")
    assert build_stats(JOB, [obs(0, t)], 1280, 720, PARAMS).stats["players_tracked"] == 0


# ---- settings ----


def test_metrics_params_come_from_settings():
    s = Settings(
        app_env="dev",
        app_origin="http://x",
        database_url="",
        git_sha="",
        jitter_px=3.0,
        tracker_max_age=7,
        heatmap_grid_w=16,
        heatmap_grid_h=9,
        possession_dist_ratio=0.8,
        possession_min_frames=2,
    )
    assert metrics_params(s) == MetricsParams(3.0, 7, 16, 9, 0.8, 2)


@pytest.mark.parametrize(
    "override",
    [
        {"jitter_px": -1.0},
        {"heatmap_grid_w": 0},
        {"heatmap_grid_h": 1000},
        {"possession_dist_ratio": 0.0},
        {"possession_min_frames": 0},
    ],
)
def test_bad_metrics_settings_rejected(override):
    s = Settings(app_env="dev", app_origin="http://x", database_url="", git_sha="", **override)
    with pytest.raises(RuntimeError, match="JITTER|HEATMAP|POSSESSION"):
        validate_settings(s)
