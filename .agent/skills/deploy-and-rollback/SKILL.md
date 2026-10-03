---
name: deploy-and-rollback
description: Plans and executes hosting for the analyzer on a cheap host (default Fly.io web + worker process groups, Neon Postgres, S3-compatible object storage such as Tigris or Cloudflare R2), including Dockerfile, docker-compose one-command local setup, /health design, Google OAuth redirect setup, secrets, day-1 YouTube-blocking spike and a documented rollback path. Use for Docker, hosting, deploy checklists and rollback.
---

# Deploy & rollback

## Target topology (default - confirm in T-003, record D-xxx)
```
Fly app "spa-<name>":  process group web (1 machine, 512 MB) | worker (1 machine, 1–2 GB, shared-cpu-2x)
Neon Postgres (free tier, TLS, reachable from GitHub Actions for migrations)
Object storage: Fly Tigris (S3 API) or Cloudflare R2 → BLOB_BACKEND=s3
Image: ghcr.io/<owner>/<repo>:<sha>
```
Why separate storage: web and worker run on different machines, so a local disk isn't shared.
GHCR pull by Fly: simplest is making the GHCR package **public** (image holds no secrets);
otherwise configure registry auth. Record the choice.
Alternatives to mention in ADR: Render (background workers are paid), Railway (usage-based),
AWS free tier (more setup). Free tiers change, check current pricing on day 1.

## Dockerfile (multi-stage sketch)
```dockerfile
FROM node:22-slim AS web
WORKDIR /fe
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates curl \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
ARG MODEL_URL
ARG MODEL_SHA256
RUN curl -fsSL "$MODEL_URL" -o /models/yolox_s.onnx --create-dirs \
 && echo "$MODEL_SHA256  /models/yolox_s.onnx" | sha256sum -c -
COPY backend/ ./
COPY --from=web /fe/dist ./static
ARG GIT_SHA=dev
ENV GIT_SHA=$GIT_SHA MODEL_PATH=/models/yolox_s.onnx PYTHONUNBUFFERED=1
RUN useradd -m app && mkdir -p /data && chown app /data
USER app
EXPOSE 8080
HEALTHCHECK CMD curl -fsS http://localhost:8080/health || exit 1
CMD ["uvicorn", "app.entrypoints.api:app", "--host", "0.0.0.0", "--port", "8080"]
```
(Set MODEL_URL/MODEL_SHA256 defaults as ARG values once verified.) Note: yt-dlp is a pip dep
(pinned) so it ships in the image.

## docker-compose.yml (the one command: `docker compose up --build`)
Services: `db` (postgres:16 + healthcheck), `migrate` (same image, `alembic upgrade head`,
`depends_on: db: condition: service_healthy`), `web` (port 8000→8080, depends on migrate
`service_completed_successfully`), `worker` (`python -m app.entrypoints.worker`), volume `blobs`
mounted at `/data` for both web and worker (`BLOB_BACKEND=local`). `env_file: .env`.

## /health
`{"status":"ok","db":"ok","version":"<GIT_SHA>"}` 200 when `SELECT 1` works, else 503
`{"status":"degraded","db":"error"}`. No auth, no secrets, fast (<100 ms), rate-limit exempt.
CD smoke test checks `status` and that `version` equals the deployed sha.

## First-deploy checklist
- `fly launch --no-deploy`, fly.toml with `[processes]` web/worker and `http_service` on web only,
  `force_https = true`, `min_machines_running = 1` (auto-stop would kill the worker/polling UX).
- `fly secrets set GOOGLE_CLIENT_ID=… GOOGLE_CLIENT_SECRET=… SESSION_SECRET=… DATABASE_URL=… S3_*…`
- Google console: add `https://<app>.fly.dev/auth/callback`; OAuth consent screen **In production**
  so any Google account (reviewers' second user) can log in.
- GitHub → Settings → Environments → `production`: secrets `DATABASE_URL`, `FLY_API_TOKEN`
  (deploy token scoped to the app: `fly tokens create deploy`), vars `FLY_APP`, `APP_URL`.
- **Day-1 spike:** from the prod worker run `yt-dlp --dump-single-json` on a sample URL
  (`fly ssh console -s -C "…"`) to learn whether YouTube blocks the host. Record outcome in ADR.

## Rollback path (ADR section)
1. Code: run `Rollback` workflow with the last good sha (images are immutable per sha), or
   `flyctl deploy --image ghcr.io/<owner>/<repo>:<sha>`. ~2 min.
2. Schema: migrations are expand/contract, so the previous image runs on the new schema; we do
   not auto-downgrade. If a migration itself is bad: `alembic downgrade -1` manually after
   verifying the downgrade script in staging/local.
3. Verify `/health` + one acceptance flow.
