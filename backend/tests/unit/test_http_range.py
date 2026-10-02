import pytest

from app.core.http_range import parse_range
from app.errors import RangeNotSatisfiableError

SIZE = 1000


@pytest.mark.parametrize(
    "header,expected",
    [
        ("bytes=0-99", (0, 99)),
        ("bytes=100-", (100, 999)),
        ("bytes=-200", (800, 999)),  # suffix: the last 200 bytes
        ("bytes=900-5000", (900, 999)),  # end past the file is clamped
        ("bytes=-5000", (0, 999)),  # suffix longer than the file = whole file
        ("bytes=999-999", (999, 999)),
        (" bytes = 0 - 9 ", (0, 9)),
    ],
)
def test_parse_single_ranges(header, expected):
    assert parse_range(header, SIZE) == expected


@pytest.mark.parametrize(
    "header",
    [None, "", "items=0-9", "bytes=abc", "bytes=9-0", "bytes=0-9,20-29", "bytes=-", "bytes=1-2-3"],
)
def test_missing_malformed_or_multi_range_means_full_response(header):
    # RFC 9110: a server MAY ignore a Range it can't or won't serve and send 200 with everything.
    assert parse_range(header, SIZE) is None


@pytest.mark.parametrize("header", ["bytes=1000-", "bytes=5000-6000", "bytes=-0"])
def test_unsatisfiable_range_is_416(header):
    with pytest.raises(RangeNotSatisfiableError) as e:
        parse_range(header, SIZE)
    assert e.value.status_code == 416


def test_empty_file_any_range_is_416():
    with pytest.raises(RangeNotSatisfiableError):
        parse_range("bytes=0-", 0)
