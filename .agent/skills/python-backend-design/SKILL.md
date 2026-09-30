---
name: python-backend-design
description: Enforces ONE consistent design style (layered architecture with a functional core) for any Python backend code — data/ML/AI pipelines, ETL jobs, batch scripts, workers, and web APIs (FastAPI, Flask). Use this skill whenever the user asks to write, scaffold, refactor, extend, or review Python backend code, a pipeline, a service, an API, a worker, or a multi-file Python project, even if they don't mention "design" or "architecture". Also use it when adding a feature to an existing Python backend, so new code doesn't introduce a second design style.
---

# Python Backend Design — One Way To Build It

The main risk in a growing Python backend is not bad patterns. It is *too many* patterns: one module uses ABC hierarchies, another uses factories, a third uses a singleton, and a fourth uses free functions with globals. Each choice is defensible on its own, but together they make the codebase hard to read, test, and extend.

This skill fixes that by choosing **one** style and a **closed set of building blocks**. When you write backend code, pick from this set only. If something seems to need a different pattern, first try to express it with the allowed blocks (the lookup table below almost always has an answer). Only step outside the set when there is a concrete reason, and state that reason in a code comment.

## The style: layered architecture with a functional core

```
project/
├── config.py          # UPPERCASE config variables + frozen Settings dataclass
├── errors.py          # one AppError base + a few subclasses
├── core/              # PURE: domain dataclasses + pure functions. No I/O.
│   ├── models.py      # frozen dataclasses (domain objects)
│   ├── ports.py       # typing.Protocol interfaces for external things
│   └── <topic>.py     # pure business/transform logic
├── adapters/          # I/O: classes that talk to DBs, files, HTTP, models, queues
│   └── <system>.py    # each class satisfies a Protocol from core/ports.py
├── services/          # ORCHESTRATION: plain functions wiring core + adapters
│   └── <usecase>.py
├── wiring.py          # composition root: build_container(settings) -> Container
└── entrypoints/       # THIN: main.py (pipeline/CLI), api.py (web), schemas.py
```

Small projects can collapse folders into single files (`core.py`, `adapters.py`, `services.py`), but the **layers and the rules stay the same**.

### Dependency direction (never violated)

```
entrypoints → wiring → services → core ← adapters
```

- `core` imports nothing from the project except `errors`. It does no I/O: no file access, network calls, DB access, environment reads, `print`, or `time.now()` (pass time in as an argument).
- `adapters` import `core` (for models and Protocols) and never import `services` or `entrypoints`.
- `services` import `core` and receive adapters **as parameters typed with the Protocol**. They never import concrete adapter classes.
- Only `wiring.py` and `entrypoints` know about concrete adapters.

This direction is why the style stays testable. Pure core functions need no mocks, and services can be tested with tiny fake adapters.

## The closed set of building blocks

| Building block | Where | Use it for |
|---|---|---|
| `@dataclass(frozen=True, slots=True)` | core/models.py, config.py | All domain data and settings |
| Pure function | core/ | All business logic and data transforms |
| `typing.Protocol` | core/ports.py | Interface for anything external |
| Adapter class | adapters/ | Wrapping one external system; holds its client/connection |
| Service function | services/ | One use case: calls core functions and adapter methods in order |
| `Container` dataclass + `build_container()` | wiring.py | Constructing adapters once from Settings |
| `dict` registry | wiring.py | Choosing between implementations by name |
| `AppError` subclasses | errors.py | All expected failures |
| `logging.getLogger(__name__)` | services/, adapters/, entrypoints/ | All logging |

Pydantic models are allowed **only** in `entrypoints/schemas.py` for HTTP request/response validation. Convert them to core dataclasses immediately at the boundary.

### Not allowed (these are the sprawl patterns)

Do not use any of the following:

- ABC or `abstractmethod` hierarchies. Use `Protocol` instead.
- Inheritance chains or mixins. Inheriting from `AppError` is the only permitted inheritance.
- Factory classes, abstract factories, or builder classes. Use a dict registry or a plain function.
- Singletons, module-level mutable state, or the `global` keyword.
- Service locators, DI frameworks, and decorator-based injection. Pass dependencies explicitly.
- Metaclasses, `__getattr__` magic, and dynamic imports.
- Chain-of-responsibility, observer, or visitor frameworks. Write explicit function calls in order.
- "Manager", "Handler", "Helper", or "Utils" god classes. Use a module of functions.
- `argparse`, `click`, or `sys.argv` parsing (see Config below).
- Mixing sync and async in one call chain.

## Decision lookup: "I need X" → use Y

| I need… | Use |
|---|---|
| Swap implementations (e.g. OpenAI vs local embedder, S3 vs disk) | A Protocol in `core/ports.py`, one adapter per implementation, and a `dict` registry in `wiring.py` keyed by a config value |
| A multi-step pipeline | A service function that calls stage functions one after another, explicitly. Stages are pure core functions or single adapter calls. |
| Retry, caching, or timing | A small function decorator in the adapter module that uses it (or `tenacity`/`functools.lru_cache`). Never on core functions that should stay pure. |
| Shared state across a run | Pass it explicitly as a dataclass argument, or return it. No globals. |
| A DB connection or HTTP client reused across calls | A field on the adapter instance, created once in `build_container()` |
| Validation of input data | A pure `validate_x(x) -> X` function in core that raises a `ValidationError(AppError)`. Pydantic only at the HTTP boundary. |
| Different behavior by type or kind | A `dict[str, Callable]` dispatch table or `match` statement. No class hierarchy. |
| Configuration | `config.py` variables → `Settings` (see below) |
| Batch or parallel processing | `concurrent.futures` inside the service function. The core stays single-item and pure. |
| Background or scheduled jobs | Another entrypoint that calls the same service functions |

If a need isn't in this table, pick the simplest option that fits the building-block set and add it to the project's notes. Do not invent a new pattern per case.

## Config: variables, not argument parsers (env-driven for this project)

All config and input values are UPPERCASE variables at the top of `backend/app/config.py`.
The assignment requires *all configuration via env vars*, so each variable reads `os.environ`
with a safe default; they are collected into a frozen `Settings` dataclass. Never use argparse,
click, typer or sys.argv unless the user explicitly asks for a CLI.

```python
# backend/app/config.py
import os
from dataclasses import dataclass

# ---- runtime / infra ----
APP_ENV = os.getenv("APP_ENV", "dev")                 # dev | prod
APP_ORIGIN = os.getenv("APP_ORIGIN", "http://localhost:8000")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://app:app@db:5432/app")
BLOB_BACKEND = os.getenv("BLOB_BACKEND", "local")     # local | s3
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() == "true"
# ---- limits ----
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "100"))
MAX_VIDEO_SECONDS = int(os.getenv("MAX_VIDEO_SECONDS", "60"))
# ---- pipeline ----
SAMPLE_FPS = float(os.getenv("SAMPLE_FPS", "5"))
DETECT_CONF = float(os.getenv("DETECT_CONF", "0.35"))
TRACK_MAX_AGE = int(os.getenv("TRACK_MAX_AGE", "15"))
# ... every other tunable listed in rule 13-cv-pipeline

@dataclass(frozen=True, slots=True)
class Settings:
    app_env: str
    app_origin: str
    database_url: str
    # ... one field per variable
    google_client_id: str
    google_client_secret: str
    session_secret: str

def load_settings() -> Settings:
    return Settings(
        app_env=APP_ENV, app_origin=APP_ORIGIN, database_url=DATABASE_URL,
        # secrets: required, no defaults, read only here
        google_client_id=os.environ["GOOGLE_CLIENT_ID"],
        google_client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        session_secret=os.environ["SESSION_SECRET"],
    )
```

Only `config.py` touches the environment. Tests build `Settings(...)` directly.

## Project adaptations (Sports Play Analyzer)

- DB access uses SQLAlchemy **Core** `Table` objects in `adapters/db_tables.py` (no ORM
  declarative classes — they require inheritance). Alembic `env.py` imports that `MetaData`.
- FastAPI middleware is written as functions (`@app.middleware("http")`), not
  `BaseHTTPMiddleware` subclasses, so the checker stays clean.
- The worker is a second entrypoint (`entrypoints/worker.py`) calling the same services.
- Protocols in `core/ports.py`: `JobRepo`, `ResultRepo`, `UserRepo`, `SessionRepo`, `BlobStore`,
  `FrameSource`, `FrameSink`, `Detector`, `UrlMediaFetcher`, `Clock`.

## Sync vs async

Default to **sync everywhere**. FastAPI routes should be plain `def`, which FastAPI runs in a threadpool. Go async only when the user needs high-concurrency I/O, and then make the **entire chain** async (entrypoint → service → adapter). Never call `asyncio.run` inside a service, and never mix the two in one chain.

## Errors and logging

- `errors.py` defines `class AppError(Exception)` plus a handful of subclasses such as `ValidationError`, `NotFoundError`, and `ExternalServiceError`.
- Adapters catch library exceptions and re-raise them as `ExternalServiceError(...) from e`.
- Entrypoints are the only place that catches `AppError` broadly. `main.py` logs it and exits non-zero. `api.py` maps it to an HTTP status in a single exception handler.
- Never use bare `except:`, and never swallow errors silently.
- Use `logger = logging.getLogger(__name__)` per module. Configure logging once in the entrypoint. No `print` outside entrypoints.

## Typing and naming

- Type-hint every function signature. Use `list[X]` and `X | None` (Python 3.10+).
- Modules are nouns (`chunking.py`, `vector_store.py`). Functions are verbs (`chunk_document`, `embed_chunks`). Adapters are named `<System><Role>`, e.g. `PostgresDocumentRepo` or `OpenAIEmbedder`.
- Protocols describe roles: `DocumentRepo`, `Embedder`, `BlobStore`.

## Working on existing code

- **If the project is already consistent in a different style**, match that style instead of imposing this one. Mention to the user that this skill's style differs, and ask whether they want to migrate.
- **If the project is already a mix of styles**, write new code in this style. Don't rewrite unrelated code unasked; briefly suggest which modules would be worth migrating.
- **When reviewing code**, report violations grouped by rule, citing the rule from this file and giving a concrete fix.

## Workflow when writing backend code

1. Identify the use cases. Each becomes a service function.
2. Identify the external systems. Each becomes a Protocol and an adapter.
3. Write the core models and pure functions first, then the adapters, services, wiring, and entrypoints.
4. For a new project, use the templates in `references/templates.md`. There is a pipeline example and an API example, and they share the same core, services, and wiring.
5. Run the checker on the generated code and fix anything it reports:
   ```bash
   python -c "import sys; sys.path.insert(0, '.agent/skills/python-backend-design/scripts'); import check_design; sys.exit(check_design.main('backend/app'))"
   ```
   The checker catches mechanical violations such as layer imports, ABCs, argparse, globals, and I/O in core. It does not judge design quality, so still read your code against the rules above.
6. In your reply, briefly name the layers you created, so the user can see the structure at a glance.

For small one-file scripts under about 150 lines, keep the same ideas inside one file: config variables at the top, then dataclasses, pure functions, one adapter class per external system, a `run()` service function, and a `main()` entrypoint. Don't create folders a tiny script doesn't need.

See `references/templates.md` for full worked examples.
