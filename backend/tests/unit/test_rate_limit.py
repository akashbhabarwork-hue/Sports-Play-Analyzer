import pytest

from app.adapters.memory_rate_limiter import InMemoryRateLimiter
from app.core.models import RateLimits
from app.core.rate_limit import check_window, prune


def test_window_allows_up_to_the_limit():
    assert check_window([1.0, 2.0], now=3.0, limit=3, window_s=60) == (True, 0)


def test_window_blocks_at_the_limit_and_says_when_a_slot_frees():
    # Oldest of the 3 recent hits was at t=10 → a slot frees at t=70; now=40 → wait 30 s.
    assert check_window([10.0, 20.0, 30.0], now=40.0, limit=3, window_s=60) == (False, 30)


def test_retry_after_is_at_least_one_second():
    assert check_window([10.0], now=69.9, limit=1, window_s=60) == (False, 1)


def test_prune_drops_hits_older_than_the_window():
    # A hit exactly window_s ago has just expired, the same instant Retry-After points to.
    assert prune([1.0, 50.0, 51.0, 100.0], now=110.0, window_s=60) == [51.0, 100.0]


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


LIMITS = RateLimits(per_minute=10, per_hour=30)


def test_rate_limit_eleventh_submit_in_a_minute_is_refused():
    clock = FakeClock()
    limiter = InMemoryRateLimiter(LIMITS, clock=clock)
    for _ in range(10):
        assert limiter.hit("alice") == 0
        clock.t += 1
    assert limiter.hit("alice") > 0


def test_rate_limit_is_per_user():
    limiter = InMemoryRateLimiter(LIMITS, clock=FakeClock())
    for _ in range(10):
        limiter.hit("alice")
    assert limiter.hit("alice") > 0
    assert limiter.hit("bob") == 0


def test_rate_limit_minute_window_recovers():
    clock = FakeClock()
    limiter = InMemoryRateLimiter(LIMITS, clock=clock)
    for _ in range(10):
        limiter.hit("alice")
    clock.t += 61
    assert limiter.hit("alice") == 0


def test_rate_limit_hourly_cap_applies_across_minutes():
    clock = FakeClock()
    limiter = InMemoryRateLimiter(LIMITS, clock=clock)
    for _ in range(30):
        assert limiter.hit("alice") == 0
        clock.t += 7  # 30 hits spread over ~3.5 min: never 10 in one minute
    wait = limiter.hit("alice")
    assert wait > 60  # blocked by the hourly window, not the minute one


def test_rate_limit_refused_attempts_do_not_extend_the_block():
    clock = FakeClock()
    limiter = InMemoryRateLimiter(LIMITS, clock=clock)
    for _ in range(10):
        limiter.hit("alice")
    first = limiter.hit("alice")
    for _ in range(50):
        limiter.hit("alice")  # hammering while blocked
    clock.t += first
    assert limiter.hit("alice") == 0


@pytest.mark.parametrize("bad", [RateLimits(0, 30), RateLimits(10, 5)])
def test_rate_limits_must_be_sane(bad):
    with pytest.raises(ValueError):
        InMemoryRateLimiter(bad)
