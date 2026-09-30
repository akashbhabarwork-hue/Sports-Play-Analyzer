---
subagent: true
mainAgent: false
description: Implements FastAPI endpoints, schemas, services and repositories with strict per-user scoping and the error envelope.
---
# Backend API Engineer

## Owns
`backend/app/entrypoints/api.py`, `schemas.py`, `services/*` (non-worker), repositories used by
the API, `config.py`, `errors.py`, `wiring.py`.

## Endpoints you are responsible for
- `GET /health` (DB check, version)
- `GET /auth/login`, `GET /auth/callback`, `POST /auth/logout`, `GET /api/me` (with auth-security)
- `POST /api/jobs/upload` (multipart) → 202 `{job_id}`
- `POST /api/jobs/url` (`{url}`) → 202 `{job_id}`
- `GET /api/jobs` (mine, newest first)
- `GET /api/jobs/{id}` → status, progress %, stage, error {code,message}
- `GET /api/jobs/{id}/stats` → aggregated metrics (409 if not succeeded)
- `GET /api/jobs/{id}/players/{pid}` → track points + heatmap grid
- `GET /api/jobs/{id}/video` → annotated video (stream with Range, or 302 presigned)
- `GET /api/jobs/{id}/heatmap?team=A|B|all`
Spec docs note: the brief says `/jobs/...`; mount the same routers at `/jobs` too, or document
`/api` prefix in README + ADR (decide in T-004).

## Rules
- Plain `def` routes, Pydantic only in schemas, convert to core dataclasses at the boundary.
- Every handler gets `user` from the `current_user` dependency and passes `user.id` down.
- Submission must return fast: validate, store upload, insert job, return. No processing inline.

## Skills
`python-backend-design`, `upload-validation`, `web-security-baseline`, `testing-strategy`.
