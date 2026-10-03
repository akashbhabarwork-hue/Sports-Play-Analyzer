---
trigger: always_on
---

# Project Core - Sports Play Analyzer (FalcRise Tech assignment)

## Mission
A coach uploads a football/basketball clip (≤60 s, ≤100 MB) or pastes a YouTube URL (≤60 s).
The system returns a `job_id` immediately, a background worker detects players + ball, tracks
players with stable IDs, computes tactical metrics, renders an annotated video, and the UI shows
live job status, the video, stats and per-player / per-team heatmaps.

Reviewers will test the LIVE URL with exactly these acceptance scenarios:
1. Login → submit YouTube URL → job completes → annotated video plays → one player's heatmap opens.
2. Submit a corrupt file → clean, readable failure.
3. Login as second user → first user's job is inaccessible (404).
Every decision must protect these three scenarios first.

## Source of truth
- Tickets & status: `docs/TICKETS.md` (work ONLY from tickets; never invent scope silently).
- Architecture decisions: `docs/ADR.md` (1–2 pages) + running log `docs/decisions.md`.
- Progress narrative: `docs/devlog/DEVLOG.md` and `docs/devlog/stages/`.
- AI usage evidence: `AI_USAGE.md`. Session log: `README.md` → "Session log".
- Agent personas: `.agent/agents/*.md`. Deep how-tos: `.agent/skills/*/SKILL.md`.

## Locked stack (change only via a decision entry + user approval)
| Area | Choice |
|---|---|
| Backend | Python 3.12, FastAPI with **sync `def` routes**, Uvicorn |
| DB | Postgres 16, SQLAlchemy **Core** (Table objects, no ORM classes), psycopg 3, Alembic |
| Queue | Postgres `jobs` table, `SELECT … FOR UPDATE SKIP LOCKED` + lease/heartbeat |
| Auth | Google OAuth 2.0 Authorization Code + PKCE via **Authlib**; server-side sessions, opaque id in `httpOnly; Secure; SameSite=Lax` cookie |
| Vision | Pretrained detector via ONNX Runtime (default YOLOX-S, Apache-2.0; fallback Ultralytics YOLO, AGPL, must be noted in ADR). No training. |
| Tracking | Own ByteTrack-style tracker (IoU + Hungarian via `scipy.optimize.linear_sum_assignment`), pure & unit-tested |
| Video I/O | `ffmpeg`/`ffprobe` subprocesses with **argument lists**, raw frames streamed through pipes |
| URL fetch | `yt-dlp` (argument list) for metadata; media downloaded by our own SSRF-guarded HTTP client |
| Storage | `BlobStore` protocol: local disk (compose) / S3-compatible e.g. Cloudflare R2 (prod) |
| Frontend | React + Vite + TypeScript, built into the same Docker image and served by FastAPI (same origin) |
| Ops | Docker multi-stage image, `docker compose up` one command, JSON structured logs |
| CI/CD | GitHub Actions: CI on push/PR; CD on main → GHCR → migrate → deploy → `/health` smoke |
| Host | Default Fly.io (web + worker process groups) + managed Postgres (Neon/Fly). Confirm in T-003. |

## Repository layout (monorepo)
```
backend/app/{config.py,errors.py,wiring.py}
backend/app/core/        # pure logic: tracking, metrics, heatmaps, possession, validation, url rules
backend/app/adapters/    # Postgres, blob store, ffmpeg, onnx detector, yt-dlp, http fetcher, oauth
backend/app/services/    # use cases: submit_job, process_job, read_job, auth
backend/app/entrypoints/ # api.py, schemas.py, worker.py
backend/migrations/      # Alembic
backend/tests/{unit,integration,fixtures}/
frontend/                # Vite React TS
.github/workflows/{ci.yml,cd.yml,rollback.yml}
docs/{ADR.md,TICKETS.md,decisions.md,devlog/}
Dockerfile  docker-compose.yml  .env.example  README.md  AI_USAGE.md
```

## Non-negotiables (never violate, even if asked mid-task - raise it instead)
1. Every job/video/result query is scoped by `user_id` from the session. Other users' objects → **404**.
2. No shell strings: `subprocess.run([...], shell=False)` only. Never f-string a command.
3. Secrets only from env vars. Never write a real secret into any file, log, test or commit.
4. Frames are streamed; never read a whole video into memory.
5. Submission never blocks on processing; return `202` + `job_id`.
6. Worker is idempotent: rerunning a job yields the same rows (no duplicates), no job stuck in `processing`.
7. All tunables (FPS, conf threshold, tracker params, limits) come from env vars via `config.py`.
8. Python config = UPPERCASE variables in `config.py` → frozen `Settings`. **No argparse/click/sys.argv.**
9. Core maths is pure and unit-testable with fixture detections, no model needed for tests.
10. Pin versions (Python deps, npm deps, GitHub Actions by full commit SHA).

## Effort budget
Hard cap ≈10 hours of hands-on work in a 36 h window. Prefer the simplest thing that satisfies the
acceptance criteria. Anything marked BONUS in TICKETS.md is done only after all MUST tickets are green.
When a ticket runs over its estimate by >50 %, stop and tell the user with options.
