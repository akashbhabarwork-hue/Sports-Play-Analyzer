"""HTTP `Range: bytes=…` parsing for video seeking (pure, RFC 9110 §14).

Only a single range is served; anything we don't support is ignored, which RFC 9110 allows
(the client then gets the whole file with 200). Browsers seeking in <video> send one range.
"""

import re

from ..errors import RangeNotSatisfiableError

_SINGLE = re.compile(r"^bytes\s*=\s*(\d*)\s*-\s*(\d*)$")


def parse_range(header: str | None, size: int) -> tuple[int, int] | None:
    """(start, end) inclusive, clamped to the file; None = send the whole file."""
    if not header:
        return None
    match = _SINGLE.match(header.strip())
    if not match:
        return None  # other units, multiple ranges or garbage
    first, last = match.groups()
    if not first and not last:
        return None
    if not first:  # suffix: the last N bytes
        length = int(last)
        if length == 0 or size == 0:
            raise RangeNotSatisfiableError("Requested range is not available")
        return max(0, size - length), size - 1
    start = int(first)
    end = int(last) if last else size - 1
    if last and end < start:
        return None  # invalid → ignore
    if start >= size:
        raise RangeNotSatisfiableError("Requested range is not available")
    return start, min(end, size - 1)
