"""Split players into two teams by jersey colour. Pure numpy (frames in, labels out).

For each confirmed track the pipeline samples a few torso crops (middle 40 % of the box width,
20-50 % of its height: shirt, not shorts, grass or head). Each crop becomes one colour feature;
a track's feature is the median of its samples. Two-cluster k-means then splits the tracks.

Feature: HSV as a point in the colour cone, (s·cos h, s·sin h, v). Hue is an angle, so 359°
and 1° (both red) land next to each other, and value keeps white and black kits apart even
though both have no saturation.

If the two cluster centres are closer than `min_separation`, the kits can't be told apart and
every player is "unknown". Referees and goalkeepers get whichever team they look closest to.
"""

from collections.abc import Mapping, Sequence

import numpy as np

from .models import Box

TEAM_A, TEAM_B, UNKNOWN = "A", "B", "unknown"
KMEANS_ITERATIONS = 20


def torso_region(box: Box) -> Box:
    w, h = box.x2 - box.x1, box.y2 - box.y1
    return Box(box.x1 + 0.3 * w, box.y1 + 0.2 * h, box.x1 + 0.7 * w, box.y1 + 0.5 * h)


def torso_pixels(frame: np.ndarray, box: Box) -> np.ndarray | None:
    """RGB pixels (N, 3) of the torso crop, clamped to the frame; None if nothing is left."""
    t = torso_region(box)
    fh, fw = frame.shape[:2]
    x1, x2 = max(int(t.x1), 0), min(int(round(t.x2)), fw)
    y1, y2 = max(int(t.y1), 0), min(int(round(t.y2)), fh)
    if x2 <= x1 or y2 <= y1:
        return None
    return frame[y1:y2, x1:x2, :3].reshape(-1, 3)


def rgb_to_hsv(rgb: np.ndarray) -> np.ndarray:
    """(N, 3) uint8 RGB -> (N, 3) float HSV, each channel in [0, 1] (hue as a turn fraction)."""
    c = rgb.astype(float) / 255.0
    r, g, b = c[:, 0], c[:, 1], c[:, 2]
    v = c.max(axis=1)
    delta = v - c.min(axis=1)
    s = np.where(v > 0, delta / np.maximum(v, 1e-12), 0.0)
    safe = np.maximum(delta, 1e-12)
    h = np.select(
        [delta == 0, v == r, v == g],
        [0.0, ((g - b) / safe) % 6, (b - r) / safe + 2],
        default=(r - g) / safe + 4,
    )
    return np.stack([h / 6.0, s, v], axis=1)


def colour_feature(pixels: np.ndarray) -> np.ndarray:
    """One crop -> (s·cos h, s·sin h, v) using per-channel medians (robust to stray pixels)."""
    hsv = rgb_to_hsv(pixels)
    angle = 2 * np.pi * hsv[:, 0]
    cone = np.stack([hsv[:, 1] * np.cos(angle), hsv[:, 1] * np.sin(angle), hsv[:, 2]], axis=1)
    return np.median(cone, axis=0)


def kmeans_two(points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """k=2 k-means with a deterministic farthest-point start. Returns (labels, centres)."""
    first = points[0]
    second = points[np.argmax(np.linalg.norm(points - first, axis=1))]
    centres = np.stack([first, second])
    labels = np.zeros(len(points), dtype=int)
    for _ in range(KMEANS_ITERATIONS):
        dists = np.linalg.norm(points[:, None, :] - centres[None, :, :], axis=2)
        new_labels = dists.argmin(axis=1)
        new_centres = np.stack(
            [
                points[new_labels == k].mean(axis=0) if np.any(new_labels == k) else centres[k]
                for k in range(2)
            ]
        )
        if np.array_equal(new_labels, labels) and np.allclose(new_centres, centres):
            break
        labels, centres = new_labels, new_centres
    return labels, centres


def assign_teams(
    samples: Mapping[int, Sequence[np.ndarray]], min_separation: float
) -> dict[int, str]:
    """Public id -> "A" | "B" | "unknown". `samples` holds each track's crop features.

    Team A is the cluster containing the lowest player id, so labels don't flip between runs.
    """
    ids = sorted(samples)
    labels = {pid: UNKNOWN for pid in ids}
    usable = [pid for pid in ids if len(samples[pid]) > 0]
    if len(usable) < 2:
        return labels
    points = np.stack([np.median(np.stack(samples[pid]), axis=0) for pid in usable])
    cluster, centres = kmeans_two(points)
    if np.linalg.norm(centres[0] - centres[1]) < min_separation or len(set(cluster)) < 2:
        return labels
    a_cluster = cluster[0]  # usable is sorted, so index 0 is the lowest id
    for pid, k in zip(usable, cluster):
        labels[pid] = TEAM_A if k == a_cluster else TEAM_B
    return labels
