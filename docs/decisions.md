# Decisions log

Running log of every meaningful choice (feeds docs/ADR.md). Format:

### D-xxx <title> (<date>, T-xxx)
Context: … | Options: A / B / C | Chosen: B | Because: … | Consequences: …

---

### D-001 Object detection model selection (2026-09-30, T-002)
Context: Need pretrained COCO detector for players and ball running on CPU worker.
Options: A (Ultralytics YOLO - AGPL-3.0) / B (YOLOX-S ONNX - Apache-2.0)
Chosen: B (YOLOX-S ONNX)
Because: Apache-2.0 licence is clean and permissive for distribution; ONNX Runtime has excellent CPU performance without PyTorch overhead; zero model training required.
Consequences: Pre-download model during Docker build; write custom letterbox and NMS post-processing in pure Python/NumPy.

### D-002 Hosting and deployment topology (2026-09-30, T-002)
Context: Need cheap/free, reliable hosting with separated web and worker processes and persistent storage.
Options: A (Render / Railway) / B (Fly.io + Neon Postgres + S3/Tigris) / C (Single VPS)
Chosen: B (Fly.io + Neon Postgres + Tigris / Cloudflare R2)
Because: Fly.io allows running separate `web` and `worker` process groups from a single multi-stage Dockerfile; Neon provides managed serverless Postgres 16; S3-compatible storage decouples video blobs from ephemeral container disks.
Consequences: Multi-region config must align DB and worker latency; presigned URLs used for video playback.

### D-003 Session and authentication strategy (2026-09-30, T-002)
Context: Secure user authentication with per-user data isolation.
Options: A (Stateless JWT in cookie/localStorage) / B (Server-side sessions in Postgres `sessions` table with `__Host-sid` cookie)
Chosen: B (Server-side sessions in Postgres)
Because: Immediate revocation on logout, avoids client-side token leakage, simplifies single-source-of-truth user lookup.
Consequences: DB lookup per authenticated request (cached per-request cycle in FastAPI dependency).

### D-004 API routing structure and legacy compatibility (2026-09-30, T-002)
Context: Brief specifies endpoints like `POST /jobs/upload` and `GET /jobs/{id}`, while SPA architectures typically namespace to `/api/`.
Options: A (`/api/...` only) / B (`/jobs/...` only) / C (`/api/jobs/...` canonical with `/jobs/...` rewrite/alias)
Chosen: C (`/api/jobs/...` canonical with `/jobs/...` aliases)
Because: Satisfies reviewer curl commands hitting `/jobs/...` while maintaining clean dev proxy separation for Vite SPA under `/api/`.
Consequences: Route definitions in FastAPI map both `/api/jobs` and `/jobs`.

### D-005 OAuth provider and PKCE protocol (2026-09-30, T-002)
Context: Authentication requirement for login.
Options: A (Custom username/password) / B (Google OAuth 2.0 Authorization Code Flow + PKCE)
Chosen: B (Google OAuth 2.0 + PKCE via Authlib)
Because: Satisfies assignment requirement using a vetted standard library; PKCE prevents authorization code interception attacks.
Consequences: Requires Google Client ID and Secret in environment; ephemeral session cookie for OAuth state handshake.

### D-006 Live job status polling mechanism (2026-09-30, T-002)
Context: Frontend needs to show real-time progress as jobs process.
Options: A (WebSockets) / B (Server-Sent Events) / C (Client-side polling every 2s while active)
Chosen: C (Client-side polling)
Because: Stateless, simplest to implement and debug, resilient across worker restarts and proxy dropouts, automatically pauses when tab is hidden.
Consequences: Slightly higher request count while jobs run; SSE deferred to bonus ticket T-B03.

### D-007 Stop ignoring `*.ts` in .gitignore (2026-10-01, T-013)
Context: `.gitignore` listed `*.ts` (meant for MPEG transport-stream video), which silently excluded every TypeScript source (`vite.config.ts`, `vite-env.d.ts`, `api.ts`) from the repo, so a fresh clone could not typecheck or build.
Options: A (keep `*.ts`, add `!frontend/**/*.ts` negations) / B (drop `*.ts`; ignore only `*.m2ts`/`*.mts`, rely on `/data/`, `blobs/`, `storage/` dir ignores for stray media)
Chosen: B
Because: video only ever lands in the already-ignored blob/data dirs; a wildcard that collides with a source extension is a trap for every future `.ts` file.
Consequences: recreated the three lost frontend files; CI frontend job now proves a fresh clone builds.

### D-008 SPA directory from `STATIC_DIR` env var (2026-10-01, T-013)
Context: `api.py` hard-coded `<repo>/frontend/dist`, but the Docker image copies the build to `/app/backend/static`, so production never served the UI; the SPA test also depended on a local build existing.
Options: A (change the Docker copy path) / B (`STATIC_DIR` setting, default `<repo>/frontend/dist`, Dockerfile sets `/app/backend/static`)
Chosen: B
Because: follows "all configuration via env vars" and lets tests point at a temp dir with a fake `index.html`.
Consequences: `Settings.static_dir`; unit tests no longer need `npm run build` first.

### D-009 CI shape (2026-10-01, T-013)
Context: Brief requires CI on every push and PR (lint, test, build), least privilege and pinned actions.
Chosen: three jobs — backend (ruff lint+format, design checker, unit, integration with Postgres 16 service), frontend (eslint, `tsc -b`, build on Node 20 to match the Dockerfile), docker (buildx build with GHA cache, no push, then run the image against Postgres and smoke `/health` + SPA root). Top-level `permissions: {}`, `contents: read` per job, `persist-credentials: false`, every action pinned to a 40-char commit SHA resolved with `git ls-remote` (checkout v7.0.1, setup-python v7.0.0, setup-node v7.0.0, setup-buildx v4.4.1, build-push v7.4.0); per-ref concurrency cancels superseded runs.
Because: the docker smoke run catches image/entrypoint breakage that a build-only job misses (it did: the `app.entrypoints.api:app` target did not exist).
Consequences: integration step treats pytest exit 5 ("no tests collected") as success until T-020 adds integration tests — remove that allowance then.
