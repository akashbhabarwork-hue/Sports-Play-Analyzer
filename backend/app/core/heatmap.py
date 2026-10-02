"""Position heatmaps on a coarse grid. Pure.

A heatmap is the JSON the API serves: {"w": GW, "h": GH, "counts": [...], "max": n}, with
`counts` flat and row-major (index = row * GW + col). Points are normalised (0..1) feet
positions, so grids from different resolutions are comparable.
"""

from collections.abc import Iterable
from typing import Any


def heatmap_cell(nx: float, ny: float, grid_w: int, grid_h: int) -> tuple[int, int]:
    """(col, row) for a normalised point; the right/bottom edge (1.0) falls in the last cell
    and points slightly outside the frame (boxes cut by the border) are clamped in."""
    col = min(max(int(nx * grid_w), 0), grid_w - 1)
    row = min(max(int(ny * grid_h), 0), grid_h - 1)
    return col, row


def build_heatmap(
    points: Iterable[tuple[float, float]], grid_w: int, grid_h: int
) -> dict[str, Any]:
    counts = [0] * (grid_w * grid_h)
    for nx, ny in points:
        col, row = heatmap_cell(nx, ny, grid_w, grid_h)
        counts[row * grid_w + col] += 1
    return {"w": grid_w, "h": grid_h, "counts": counts, "max": max(counts, default=0)}


def sum_heatmaps(maps: Iterable[dict[str, Any]], grid_w: int, grid_h: int) -> dict[str, Any]:
    """Cell-wise sum (team = its players; "all" = everyone). Empty input -> all zeros."""
    counts = [0] * (grid_w * grid_h)
    for m in maps:
        if (m["w"], m["h"]) != (grid_w, grid_h):
            raise ValueError("heatmap grid sizes differ")
        counts = [a + b for a, b in zip(counts, m["counts"])]
    return {"w": grid_w, "h": grid_h, "counts": counts, "max": max(counts, default=0)}
