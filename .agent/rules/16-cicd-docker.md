---
trigger: model_decision
description: Apply when editing Dockerfile, docker-compose, GitHub Actions workflows, deployment config (fly.toml etc.), health checks, migrations-on-deploy, registry pushes or rollback procedures.
---

# CI/CD & Docker rules

Deep guides: skills `github-actions-cicd`, `deploy-and-rollback`.

## Docker
- One multi-stage `Dockerfile`: stage 1 builds frontend (node, `npm ci`), stage 2 python slim with
  `ffmpeg` from apt, installs pinned backend deps, copies frontend `dist/`, runs as non-root user.
- Same image, two commands: web (`uvicorn app.entrypoints.api:app`) and worker
  (`python -m app.entrypoints.worker`).
- `docker compose up --build` = the one command: postgres (healthcheck), migrate (one-shot
  `alembic upgrade head`), web, worker, shared volume for local blobs.
- `HEALTHCHECK` hits `/health`. `/health` returns 200 only if DB `SELECT 1` succeeds; includes
  git sha/version.

## GitHub Actions
- `ci.yml` on `push` and `pull_request`: backend (ruff, pytest unit + integration with postgres
  service), frontend (eslint, tsc, build), docker build (no push).
- `cd.yml` on push to `main` only, `environment: production`, `concurrency` group, steps:
  build → push GHCR (`:sha` and `:main`) → run migrations → deploy image by sha → smoke test
  `/health` with retries; job fails if unhealthy.
- `rollback.yml` (`workflow_dispatch`, input image sha) redeploys a previous image.
- Top-level `permissions: {}` then least privilege per job (`contents: read`, `packages: write`
  only where pushing).
- Every `uses:` pinned to a full 40-char commit SHA with a `# vX.Y.Z` comment. Never invent SHAs:
  resolve with `git ls-remote https://github.com/<owner>/<repo> refs/tags/<tag>` (dereference
  annotated tags with `^{}`) or ask the user.
- Secrets come from GitHub Environment `production` secrets, never repo files.
