"""Worker loop with fakes: claim → process, transient errors survive, graceful stop."""

import signal
import threading
from types import SimpleNamespace

import pytest

from app.core.pipeline import poll_delay
from app.entrypoints import worker
from app.errors import ExternalServiceError

# ---- poll_delay (pure) ----


@pytest.mark.parametrize("u,expected", [(0.0, 1.5), (0.5, 2.0), (1.0, 2.5)])
def test_poll_delay_spreads_plus_minus_jitter(u, expected):
    assert poll_delay(2.0, 0.25, u) == pytest.approx(expected)


def test_poll_delay_never_negative():
    assert poll_delay(0.1, 5.0, 0.0) >= 0


# ---- run_once / run_forever (fakes) ----


class FakeQueue:
    def __init__(self, jobs=()):
        self.jobs = list(jobs)
        self.sweeps = 0

    def sweep_dead(self):
        self.sweeps += 1
        return 0

    def claim(self, worker_id, lease_s):
        return self.jobs.pop(0) if self.jobs else None


def make_ctx(queue, process):
    cfg = SimpleNamespace(lease_s=60)
    return worker.WorkerContext(queue=queue, ports=None, cfg=cfg, worker_id="w1",
                                poll_seconds=0.01, process=process)  # fmt: skip


def test_run_once_returns_none_when_queue_is_empty():
    q = FakeQueue()
    assert worker.run_once(make_ctx(q, lambda *a: "succeeded")) is None
    assert q.sweeps == 1  # dead jobs are swept on every poll


def test_run_once_processes_a_claimed_job():
    seen = []
    job = SimpleNamespace(id="job-1", user_id="u", attempts=1)
    ctx = make_ctx(FakeQueue([job]), lambda j, ports, cfg, wid: seen.append((j.id, wid)) or "ok")
    assert worker.run_once(ctx) == "ok"
    assert seen == [("job-1", "w1")]


def test_run_once_survives_transient_errors_so_the_lease_can_lapse():
    def boom(*a):
        raise ExternalServiceError("storage unavailable")

    job = SimpleNamespace(id="job-1", user_id="u", attempts=1)
    assert worker.run_once(make_ctx(FakeQueue([job]), boom)) == "error"


def test_run_once_survives_unexpected_bugs_too():
    def boom(*a):
        raise KeyError("bug")

    job = SimpleNamespace(id="job-1", user_id="u", attempts=1)
    assert worker.run_once(make_ctx(FakeQueue([job]), boom)) == "error"


class DownQueue(FakeQueue):
    """Database unreachable: every queue call fails like PostgresJobQueue's db_errors wrapper."""

    def sweep_dead(self):
        raise ExternalServiceError("database unavailable")


def test_run_once_treats_database_outage_as_idle_instead_of_crashing():
    assert worker.run_once(make_ctx(DownQueue(), lambda *a: "succeeded")) is None


def test_run_forever_keeps_polling_through_a_database_outage():
    stop = threading.Event()
    polls = []

    class FlakyQueue(FakeQueue):
        def sweep_dead(self):
            polls.append(1)
            if len(polls) == 3:
                stop.set()
            raise ExternalServiceError("database unavailable")

    worker.run_forever(make_ctx(FlakyQueue(), lambda *a: "succeeded"), stop)
    assert len(polls) == 3  # still alive after two failed polls


def test_run_forever_drains_queue_then_stops_when_asked():
    jobs = [SimpleNamespace(id=f"j{i}", user_id="u", attempts=1) for i in range(3)]
    done = []
    stop = threading.Event()

    def process(job, *a):
        done.append(job.id)
        if len(done) == 3:
            stop.set()  # e.g. SIGTERM arrives while the last job runs
        return "succeeded"

    worker.run_forever(make_ctx(FakeQueue(jobs), process), stop)
    assert done == ["j0", "j1", "j2"]


def test_run_forever_finishes_current_job_before_stopping():
    stop = threading.Event()
    stop.set()  # already asked to stop: no new job is claimed
    q = FakeQueue([SimpleNamespace(id="j0", user_id="u", attempts=1)])
    worker.run_forever(make_ctx(q, lambda *a: "succeeded"), stop)
    assert len(q.jobs) == 1


def test_stop_handler_sets_the_event():
    stop = threading.Event()
    worker.install_stop_handlers(stop)
    try:
        signal.raise_signal(signal.SIGINT)
        assert stop.is_set()
    finally:
        signal.signal(signal.SIGINT, signal.default_int_handler)
