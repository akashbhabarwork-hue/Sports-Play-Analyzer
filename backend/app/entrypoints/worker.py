"""Worker process: sweep dead jobs → claim one (SKIP LOCKED) → process it → repeat (T-063).

Run with `python -m app.entrypoints.worker` (compose `worker` service; Fly worker group).

Crash safety comes from the queue, not from this loop: a claimed job carries a lease that
process_job's heartbeats extend. If this process dies (OOM, deploy, kill -9), the lease lapses
and any worker reclaims the job; results are replaced in one transaction and blob keys are
deterministic, so a rerun never duplicates rows. After max_attempts the sweep marks it
WORKER_CRASHED, so no job stays "processing" forever.

SIGTERM/SIGINT: finish the current job, then exit. If the platform kills us first, the
lease lapses and the job is retried: the same path as a crash.
"""

import logging
import random
import signal
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..config import load_settings
from ..core.pipeline import poll_delay
from ..core.ports import JobQueue
from ..errors import AppError, ExternalServiceError
from ..services.process import process_job
from ..wiring import build_container, build_detector, build_pipeline_ports, process_config
from .log_config import setup_logging

logger = logging.getLogger(__name__)

POLL_JITTER = 0.25  # ±25 % around WORKER_POLL_SECONDS


@dataclass(frozen=True, slots=True)
class WorkerContext:
    queue: JobQueue
    ports: Any  # services.process.PipelinePorts
    cfg: Any  # services.process.ProcessConfig
    worker_id: str
    poll_seconds: float
    process: Callable[..., str] = process_job


def run_once(ctx: WorkerContext) -> str | None:
    """One poll. Returns None when there was nothing to do, else the job's outcome.

    Errors process_job re-raises (storage, DB, bugs) are logged and swallowed: the job's
    lease then lapses and it is retried by this or another worker (D-026).
    """
    try:
        swept = ctx.queue.sweep_dead()
        job = ctx.queue.claim(ctx.worker_id, ctx.cfg.lease_s)
    except ExternalServiceError:
        # Database blip: behave as idle (wait, poll again) instead of letting the process die.
        logger.warning("queue unavailable; will retry", exc_info=True)
        return None
    if swept:
        logger.warning("jobs out of attempts marked WORKER_CRASHED", extra={"count": swept})
    if job is None:
        return None
    log = {"job_id": str(job.id), "user_id": str(job.user_id), "attempt": job.attempts}
    logger.info("job claimed", extra=log)
    try:
        return ctx.process(job, ctx.ports, ctx.cfg, ctx.worker_id)
    except Exception as e:  # broad on purpose: the loop must outlive any single job
        code = e.code if isinstance(e, AppError) else type(e).__name__
        logger.exception("job attempt failed; it will be retried", extra={**log, "error": code})
        return "error"


def run_forever(ctx: WorkerContext, stop: threading.Event) -> None:
    """Poll until `stop` is set; a job already running is always finished first."""
    logger.info("worker started", extra={"worker_id": ctx.worker_id})
    while not stop.is_set():
        if run_once(ctx) is None:
            # Event.wait instead of sleep: a stop signal wakes us immediately.
            stop.wait(poll_delay(ctx.poll_seconds, POLL_JITTER, random.random()))
    logger.info("worker stopped", extra={"worker_id": ctx.worker_id})


def install_stop_handlers(stop: threading.Event) -> None:
    def request_stop(signum: int, _frame: object) -> None:
        logger.info("stop requested; finishing the current job", extra={"signal": signum})
        stop.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, request_stop)


def main() -> int:
    setup_logging()
    settings = load_settings()
    container = build_container(settings)
    try:
        detector = build_detector(settings)  # load the model once, before taking any job
    except AppError:
        logger.exception("detector model unavailable; worker cannot start")
        return 1
    ctx = WorkerContext(
        queue=container.queue,
        ports=build_pipeline_ports(container, detector),
        cfg=process_config(settings),
        worker_id=settings.worker_id,
        poll_seconds=settings.worker_poll_seconds,
    )
    stop = threading.Event()
    install_stop_handlers(stop)
    run_forever(ctx, stop)
    return 0


if __name__ == "__main__":
    sys.exit(main())
