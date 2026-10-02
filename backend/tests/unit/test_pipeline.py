import numpy as np
import pytest

from app.core.models import PipelineParams
from app.core.pipeline import (
    PROGRESS_ANALYSE_END,
    PROGRESS_ANALYSE_START,
    PROGRESS_COMPUTING,
    PROGRESS_RENDER_END,
    PROGRESS_RENDER_START,
    PROGRESS_SAVING,
    STAGES,
    add_team_sample,
    pipeline_config,
    progress_pct,
    render_pct,
    should_sample_team,
)

PARAMS = PipelineParams(
    sample_fps=5.0,
    max_seconds=60,
    max_frame_side=1280,
    heartbeat_every_frames=10,
    team_sample_every=5,
    team_max_samples=3,
    team_min_separation=0.2,
)


def test_progress_starts_and_ends_inside_the_analysis_band():
    assert progress_pct(0, 100) == PROGRESS_ANALYSE_START
    assert progress_pct(100, 100) == PROGRESS_ANALYSE_END


def test_progress_is_monotonic_and_capped_when_estimate_is_short():
    values = [progress_pct(done, 10) for done in range(0, 25)]
    assert values == sorted(values)
    assert max(values) == PROGRESS_ANALYSE_END  # more frames than ffprobe promised: no 100 %


def test_progress_never_reaches_100_before_results_are_saved():
    assert progress_pct(10**6, 1) < 100
    assert render_pct(10**6, 1) < PROGRESS_SAVING < 100


def test_stage_bands_follow_the_stepper_order():
    # analysing → computing → rendering → saving, each band strictly after the previous one
    assert PROGRESS_ANALYSE_END < PROGRESS_COMPUTING < PROGRESS_RENDER_START
    assert render_pct(0, 100) == PROGRESS_RENDER_START
    assert render_pct(100, 100) == PROGRESS_RENDER_END < PROGRESS_SAVING
    assert STAGES == ("fetching", "analysing", "computing", "rendering", "saving")


def test_progress_handles_zero_expected():
    assert progress_pct(5, 0) == PROGRESS_ANALYSE_END


@pytest.mark.parametrize("idx,expected", [(0, True), (4, False), (5, True), (10, True)])
def test_team_sampling_every_n_frames(idx, expected):
    assert should_sample_team(idx, 5) is expected


def test_add_team_sample_caps_samples_per_player():
    samples: dict[int, list[np.ndarray]] = {}
    for i in range(5):
        add_team_sample(samples, 7, np.array([i, 0, 0], float), cap=3)
    assert len(samples[7]) == 3
    assert [s[0] for s in samples[7]] == [0, 1, 2]  # keeps the first ones; no reallocation


def test_add_team_sample_ignores_missing_feature():
    samples: dict[int, list[np.ndarray]] = {}
    add_team_sample(samples, 1, None, cap=3)
    assert samples == {}


def test_pipeline_config_snapshot_is_json_ready():
    snap = pipeline_config(PARAMS, {"tracker_high_thresh": 0.5})
    assert snap["sample_fps"] == 5.0 and snap["max_frame_side"] == 1280
    assert snap["tracker_high_thresh"] == 0.5
    assert all(isinstance(v, int | float | str | bool) for v in snap.values())
