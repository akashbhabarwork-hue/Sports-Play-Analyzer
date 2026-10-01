# Sports Play Analyzer

Upload a ≤60 s football/basketball clip or paste a YouTube link → player tracking, distance,
heatmaps, possession and an annotated video.

**Live:** `<url>`  ·  **ADR:** [docs/ADR.md](docs/ADR.md)  ·  **AI usage:** [AI_USAGE.md](AI_USAGE.md)

## Run locally (one command)
```bash
cp .env.example .env        # fill GOOGLE_CLIENT_ID/SECRET, SESSION_SECRET
docker compose up --build   # http://localhost:8000
```

## Test
```bash
docker compose up -d db
pytest -q backend/tests -m "not integration and not model"
pytest -q backend/tests -m integration
cd frontend && npm ci && npm run lint && npm run typecheck && npm run build
```

## Deploy
Merging to `main` runs `.github/workflows/cd.yml`: build → GHCR → migrate → deploy → `/health` smoke.
Rollback: Actions → Rollback → enter previous sha. First-time setup: see [docs/ADR.md](docs/ADR.md) §6.

## Configuration
| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | `postgresql://...` | Postgres connection string |
| `APP_ORIGIN` | `http://localhost:8000` | Public origin; OAuth redirect URI is `APP_ORIGIN/auth/callback` |
| `SESSION_SECRET` | `""` | Signs the short-lived `oauth_tx` cookie (OAuth state/nonce/PKCE); required in production |
| `GOOGLE_CLIENT_ID` | `""` | Google OAuth client ID; required in production (dev: login says "not configured") |
| `GOOGLE_CLIENT_SECRET` | `""` | Google OAuth client secret; required in production |
| `COOKIE_SECURE` | `true` | `true`: session cookie `__Host-sid` (Secure); `false` for local http: cookie `sid` |
| `SESSION_TTL_DAYS` | `7` | Session lifetime |
| `TRUSTED_ORIGINS` | `""` | Extra origins (comma-separated) allowed to send unsafe requests; e.g. Vite `http://localhost:5173` |
| `LEASE_SECONDS` | `60` | Worker lease on a claimed job, extended by heartbeats |
| `BLOB_BACKEND` | `local` | `local` for disk storage or `s3` for S3-compatible |
| `SAMPLE_FPS` | `5` | Video decoding sample rate (frames/sec) |
| `CONF_THRESHOLD` | `0.35` | Object detector confidence threshold |
| `MAX_VIDEO_DURATION_SECONDS` | `60` | Maximum allowed duration for processing |
| `MAX_UPLOAD_SIZE_BYTES` | `104857600` | Maximum allowed upload size (100 MB) |

## API
`GET /auth/login`, `GET /auth/callback`, `POST /auth/logout`, `GET /api/me`,
`POST /api/jobs/upload`, `POST /api/jobs/url`, `GET /api/jobs`, `GET /api/jobs/{id}`,
`GET /api/jobs/{id}/stats`, `GET /api/jobs/{id}/players/{pid}`, `GET /api/jobs/{id}/video`, `GET /health`

## Session log
| # | Start (IST) | End (IST) | Duration | What I did |
|---|---|---|---|---|
| 1 | 2026-09-30 00:50 | 2026-09-30 01:20 | 0 h 30 m | S0 kickoff, repo scaffold, doc skeletons, tooling checks |
| 2 | 2026-09-30 22:21 | (open) | | |

Total: 0 h 30 m
