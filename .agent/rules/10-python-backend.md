---
trigger: glob
globs: backend/**/*.py
---

# Python backend style (layered architecture, functional core)

Full guide + templates + checker: skill `python-backend-design`. Summary of what is enforced:

## Layers and dependency direction (never violated)
`entrypoints → wiring → services → core ← adapters`
- `core/`: frozen dataclasses + pure functions. No I/O, no env reads, no `print`, no `time.time()`
  (pass time in). Imports only stdlib, numpy/scipy and `app.errors`.
- `adapters/`: one class per external system (Postgres, blob store, ffmpeg, detector, yt-dlp,
  HTTP fetcher, OAuth). Each satisfies a `typing.Protocol` from `core/ports.py`. Wrap library
  exceptions as `ExternalServiceError(...) from e`.
- `services/`: plain functions, one per use case (`submit_upload_job`, `submit_url_job`,
  `process_job`, `get_job_for_user`, …). Receive adapters as Protocol-typed parameters.
- `wiring.py`: `build_container(settings) -> Container` constructs adapters once.
- `entrypoints/`: `api.py` (FastAPI), `schemas.py` (Pydantic, boundary only), `worker.py` (loop).

## Config — variables, not argument parsers
`backend/app/config.py` holds UPPERCASE variables read from env with safe defaults, collected into
a frozen `Settings` dataclass via `load_settings()`. Only `config.py` touches `os.environ`.
Never use argparse / click / typer / sys.argv. Secrets use `os.environ["NAME"]` (no default) so a
missing secret fails fast in prod; dev defaults live only in `.env.example`.
```python
SAMPLE_FPS = float(os.getenv("SAMPLE_FPS", "5"))
DETECT_CONF = float(os.getenv("DETECT_CONF", "0.35"))
TRACK_HIGH_THRESH = float(os.getenv("TRACK_HIGH_THRESH", "0.5"))
```

## Allowed building blocks only
frozen `@dataclass(slots=True)`, pure functions, `Protocol`, adapter classes, service functions,
`Container` + `build_container`, dict registries, `AppError` subclasses, `logging.getLogger(__name__)`.
Forbidden: ABC hierarchies, inheritance (except `AppError` subclasses, `Protocol`, Pydantic
`BaseModel` in schemas), factories/builders/managers/helpers/utils classes, singletons, `global`,
DI frameworks, metaclasses, SQLAlchemy ORM declarative classes (use Core `Table`), mixing sync+async.

## Sync by default
FastAPI routes are plain `def`. Worker is a synchronous loop. No `asyncio` in services/core/adapters.
Documented exceptions (record as a decision): the two OAuth routes (Authlib's Starlette client is
async — keep them thin and call sync services via `run_in_threadpool`) and `@app.middleware("http")`
functions, which FastAPI requires to be `async def`.

## Errors → HTTP
`errors.py`: `AppError`, `ValidationError`(422), `NotFoundError`(404), `UnauthorizedError`(401),
`PayloadTooLargeError`(413), `RateLimitedError`(429), `ExternalServiceError`(502),
`UpstreamBlockedError`(422, code `YOUTUBE_BLOCKED`). One exception handler in `api.py` maps them to
`{"error": {"code": "...", "message": "human readable"}}`. Never leak stack traces to clients.

## Logging
JSON structured logs configured once in the entrypoint (e.g. `python-json-logger` or `structlog`
with JSON renderer). Always include `job_id`, `user_id` (not email) and `stage` where relevant.
No `print` outside entrypoints. Never log tokens, cookies, secrets or full signed URLs.

## Typing & naming
Type-hint every signature; `X | None`, `list[X]`. Modules are nouns, functions verbs, adapters
`<System><Role>` (`PostgresJobRepo`, `FfmpegFrameReader`, `OnnxYoloxDetector`, `S3BlobStore`).

## Before finishing any backend ticket
Run: `ruff check backend && ruff format --check backend && pytest -q backend/tests/unit`
and the design checker:
`python -c "import sys; sys.path.insert(0,'.agent/skills/python-backend-design/scripts'); import check_design; sys.exit(check_design.main('backend/app'))"`
