"""Per-player and match metrics from per-frame observations. Pure.

The worker appends one FrameObservation per sampled frame; `build_stats` computes everything
in one pass at the end (D-022). Positions use the feet point ((x1+x2)/2, y2), the closest the
box gets to "where the player stands" on the pitch.

Distances are in pixels and relative to the frame diagonal, not metres: a broadcast camera
pans and zooms, so treat them as a comparison between players in the same clip.
"""

import math
from collections import defaultdict
from collections.abc import Mapping
from uuid import UUID

from .heatmap import build_heatmap, sum_heatmaps
from .models import FrameObservation, MatchMetrics, MetricsParams, PlayerTrack
from .possession import count_possession, feet_point

TEAMS = ("A", "B")
UNKNOWN_TEAM = "unknown"

# (frame_idx, t_s, x_px, y_px) of a player's feet in one frame.
Sample = tuple[int, float, float, float]


def path_distance(samples: list[Sample], jitter_px: float, max_gap_frames: int) -> float:
    """Distance walked along the samples, in pixels.

    Movement is measured from the last *counted* position, and only once it exceeds
    `jitter_px`: detector wobble around a standing player adds nothing, while a slow walker
    still accumulates distance. A gap of more than `max_gap_frames` missing frames is not
    bridged (we don't know the path), and counting restarts after it.
    """
    total = 0.0
    ref: Sample | None = None
    prev_frame: int | None = None
    for s in samples:
        if ref is None or prev_frame is None or s[0] - prev_frame - 1 > max_gap_frames:
            ref = s
        else:
            step = math.hypot(s[2] - ref[2], s[3] - ref[3])
            if step >= jitter_px:
                total += step
                ref = s
        prev_frame = s[0]
    return total


def pct(part: int, whole: int) -> float:
    return round(100.0 * part / whole, 1) if whole else 0.0


def ball_visible_pct(observations: list[FrameObservation]) -> float:
    return pct(sum(1 for o in observations if o.ball is not None), len(observations))


def player_samples(observations: list[FrameObservation]) -> dict[int, list[Sample]]:
    samples: dict[int, list[Sample]] = defaultdict(list)
    for obs in observations:
        for t in obs.tracks:
            if t.public_id is not None:
                x, y = feet_point(t.box)
                samples[t.public_id].append((obs.frame_idx, obs.t_s, x, y))
    return dict(sorted(samples.items()))


def build_stats(
    job_id: UUID,
    observations: list[FrameObservation],
    frame_w: int,
    frame_h: int,
    params: MetricsParams,
    teams: Mapping[int, str] | None = None,
) -> MatchMetrics:
    """Stats JSON (minus `video` and `config`, which the service adds) + one row per player.

    `teams` maps public id -> "A" | "B" | "unknown" (core.teams); missing ids are "unknown".
    """
    teams = teams or {}
    diag = math.hypot(frame_w, frame_h)
    gw, gh = params.heatmap_w, params.heatmap_h
    possession = count_possession(observations, params)

    rows: list[PlayerTrack] = []
    for pid, samples in player_samples(observations).items():
        dist = path_distance(samples, params.jitter_px, params.max_gap_frames)
        norm = [(x / frame_w, y / frame_h) for _, _, x, y in samples]
        rows.append(
            PlayerTrack(
                job_id=job_id,
                track_id=pid,
                team=teams.get(pid, UNKNOWN_TEAM),
                frames_visible=len(samples),
                distance_px=round(dist, 1),
                distance_rel=round(dist / diag, 3),
                possession_frames=possession.by_player.get(pid, 0),
                heatmap=build_heatmap(norm, gw, gh),
                track=[
                    [round(t_s, 3), round(nx, 4), round(ny, 4)]
                    for (_, t_s, _, _), (nx, ny) in zip(samples, norm)
                ],
            )
        )

    def possession_pct(frames: int) -> float:
        return pct(frames, possession.ball_frames)

    team_stats = {}
    by_team = {}
    heatmaps = {"all": sum_heatmaps((r.heatmap for r in rows), gw, gh)}
    for team in TEAMS:
        members = [r for r in rows if r.team == team]
        team_stats[team] = {
            "players": [r.track_id for r in members],
            "distance_rel_total": round(sum(r.distance_rel for r in members), 3),
        }
        by_team[team] = possession_pct(sum(r.possession_frames for r in members))
        heatmaps[team] = sum_heatmaps((r.heatmap for r in members), gw, gh)

    stats = {
        "job_id": str(job_id),
        "players_tracked": len(rows),
        "ball_visible_pct": ball_visible_pct(observations),
        "possession": {
            "by_player": [
                {"player_id": r.track_id, "pct": possession_pct(r.possession_frames)}
                for r in rows
                if r.possession_frames
            ],
            "by_team": by_team,
            "unassigned_pct": possession_pct(possession.unassigned),
        },
        "players": [
            {
                "player_id": r.track_id,
                "team": r.team,
                "distance_px": r.distance_px,
                "distance_rel": r.distance_rel,
                "frames_visible": r.frames_visible,
                "possession_pct": possession_pct(r.possession_frames),
            }
            for r in rows
        ],
        "teams": team_stats,
        "heatmaps": heatmaps,
    }
    return MatchMetrics(stats=stats, tracks=tuple(rows))
