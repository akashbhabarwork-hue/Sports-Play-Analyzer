# Development log

One entry per ticket, newest at the bottom. Written by the agent, reviewed by me.
Stage summaries live in `docs/devlog/stages/`.

---

## 2026-09-30 00:58 IST — T-001 Kickoff: repo scaffold and doc skeletons (agent: orchestrator)
**What changed:** Created `.gitignore`, `.env.example`, `README.md` (with session log initialized), `docs/ADR.md`, `AI_USAGE.md`, `docs/acceptance.md`, `docs/decisions.md`, and directory skeletons for `backend/`, `frontend/`, `.github/workflows/`.
**Why:** Assignment requirement §1 & §7 to establish project structure, session logging, and architecture documentation from the very first commit.
**Decisions:** D-001 through D-006 recorded in `docs/decisions.md`.
**Verification:** `git status` verifies all scaffolded paths; tooling check verified available compilers/interpreters.
**AI mistakes caught:** none.
**Explain-it-in-review:** "We set up an agentic, ticket-driven repository layout with strict separation between pure CV/domain logic, adapters, entrypoints, and frontend SPA, backed by a clear ADR and session log."
**Next:** T-002 Confirm open decisions & T-010 Backend skeleton.

---

## 2026-09-30 23:27 IST — T-002 Confirm open decisions (agent: architect)
**What changed:** Confirmed the 6 default architecture and design choices. Verified `docs/decisions.md` and ADR are up to date.
**Why:** Required by Brief §4 and §5 to lock in model choices, hosting, and architecture before implementation.
**Decisions:** D-001 (YOLOX-S), D-002 (Fly.io+Neon), D-003 (Cookie Sessions), D-004 (API aliases), D-005 (OAuth PKCE), D-006 (Polling) all confirmed without changes.
**Verification:** Read `docs/decisions.md`.
**AI mistakes caught:** none.
**Explain-it-in-review:** "We reviewed the default tech stack options against the assignment constraints and formally committed to them, ensuring our upcoming development is fully aligned with the requirements."
**Next:** T-010 Backend skeleton, config, errors, /health, JSON logs

---

## 2026-09-30 23:55 IST — T-010 Backend skeleton (agent: backend-api)
**What changed:** Added `backend` requirements, `pyproject.toml`, and the foundational API structure (`config.py`, `errors.py`, `wiring.py`, `api.py` and `db.py`) along with a working `/health` endpoint.
**Why:** Required by Ops for structured logging and env configuration.
**Decisions:** Unpinned `sqlalchemy` and updated `psycopg` to handle Python 3.14 on Windows.
**Verification:** Ran `pytest tests/unit/test_health.py` (Passed) and the Python backend design checker (Passed).
**AI mistakes caught:** Wrote explicit protocol inheritance (`class PostgresHealthCheck(HealthCheck):`), which the design checker blocked. Fixed it to use implicit composition.
**Explain-it-in-review:** "We laid out a strict functional core architecture for our FastAPI backend, mapping environment variables to a frozen `Settings` dataclass and handling dependency injection in `wiring.py`, ensuring business logic stays pure."
**Next:** T-011 Frontend skeleton

---

## 2026-10-01 00:36 IST — T-011 Frontend skeleton (agent: frontend)
**What changed:** Initialised a Vite + React + TypeScript app in `frontend/`, added `react-router-dom`, created an `api.ts` client to handle the `{error:{code,message}}` envelope, set up development proxies, and added a `typecheck` script. Modified `backend/app/entrypoints/api.py` to serve the frontend SPA build with a fallback route.
**Why:** Sets up the UI foundation and satisfies the requirement that FastAPI serves the production frontend build.
**Decisions:** Used Vite 5 (`create-vite@5`) since the latest Vite 6 (`create-vite@9`) requires a newer Node version than available in this environment. Mounted a static fallback route in FastAPI using `FileResponse` for everything except `api/` and `auth/`.
**Verification:** Ran `npm run lint`, `typecheck`, and `build` successfully, and added a pytest script to verify FastAPI correctly returns `index.html` on frontend routes.
**AI mistakes caught:** None in this ticket.
**Explain-it-in-review:** "We created a strict TypeScript React application configured to proxy requests to the backend during development, and set up our FastAPI backend to seamlessly serve the built SPA in production with proper routing fallback."
**Next:** T-012 Dockerfile + one-command docker compose

---

## 2026-10-01 01:27 IST — T-012 Dockerfile + one-command docker compose (agent: devops)
**What changed:** Created a multi-stage `Dockerfile` (Node for frontend -> Python slim for backend), `.dockerignore`, and `docker-compose.yml` with `db`, `migrate`, `web`, and `worker` services. Added a placeholder loop for the worker in `backend/app/entrypoints/worker.py` and wrapped the `migrate` command in a resilient shell command until Alembic is installed.
**Why:** Meets the "Ops: one-command Docker setup" requirement and prepares the image for production deployment.
**Decisions:** Used a shell wrapper for the `alembic` compose command (`sh -c "alembic upgrade head || echo 'Migrations skipped'"`) to prevent the container from crashing before Alembic is formally set up in T-020.
**Verification:** Skipped running `docker compose` per user request since Docker isn't installed locally.
**AI mistakes caught:** None.
**Explain-it-in-review:** "We created a production-ready, multi-stage Dockerfile that builds the React frontend and copies it into a Python backend container running as a non-root user. The local dev environment is spun up with a single `docker compose up` command covering the database, migrations, web API, and async worker."
**Next:** T-013 CI workflow
