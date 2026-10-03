"""Per-user submission limiter kept in the web process's memory (T-090, D-032).

Fine for one web machine (the deployment we have). Several web machines would each count
separately; a shared Postgres-backed counter is BONUS T-B05. Restarting the process resets
the counts, which only ever makes the limit more lenient.
"""

import threading
import time
from collections import deque
from collections.abc import Callable

from ..core.models import RateLimits
from ..core.rate_limit import check_window, prune

MINUTE_S = 60
HOUR_S = 3600


class InMemoryRateLimiter:
    def __init__(self, limits: RateLimits, clock: Callable[[], float] = time.monotonic):
        if limits.per_minute < 1 or limits.per_hour < limits.per_minute:
            raise ValueError("need 1 <= per_minute <= per_hour")
        self.limits = limits
        self.clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()  # FastAPI runs sync routes in a thread pool

    def hit(self, key: str) -> int:
        """Record one attempt for `key`; returns 0 if allowed, else seconds to wait.

        Refused attempts are not recorded, so hammering while blocked doesn't extend the block.
        """
        with self._lock:
            now = self.clock()
            hits = deque(prune(self._hits.get(key, ()), now, HOUR_S))
            for limit, window in (
                (self.limits.per_minute, MINUTE_S),
                (self.limits.per_hour, HOUR_S),
            ):
                allowed, wait = check_window(hits, now, limit, window)
                if not allowed:
                    self._hits[key] = hits
                    return wait
            hits.append(now)
            self._hits[key] = hits
            return 0
