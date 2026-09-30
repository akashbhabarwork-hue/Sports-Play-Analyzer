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
