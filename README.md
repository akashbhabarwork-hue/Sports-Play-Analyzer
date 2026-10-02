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

## Manual YouTube fetch check
Edit `URL` at the top of `backend/scripts/fetch_check.py`, then `cd backend && python scripts/fetch_check.py`.
It runs the production fetch path (yt-dlp metadata → SSRF-guarded download → ffprobe) without a database.

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
| `BLOB_BACKEND` | `local` | `local` (directory) or `s3` (Tigris/R2/AWS); production requires `s3` |
| `BLOB_LOCAL_DIR` | `<repo>/blobs` | Directory for `local` (Docker: `/app/blobs`) |
| `S3_ENDPOINT_URL` / `S3_BUCKET` / `S3_REGION` | `""` | S3-compatible storage; empty endpoint = AWS |
| `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY` | `""` | Storage credentials (required for `s3`) |
| `SAMPLE_FPS` | `5` | Video decoding sample rate (frames/sec) |
| `CONF_THRESHOLD` | `0.35` | Object detector confidence threshold |
| `TRACKER_HIGH_THRESH` / `TRACKER_LOW_THRESH` | `0.5` / `0.1` | Detection scores that start/match tracks vs. only keep existing tracks alive (ByteTrack stage 2) |
| `TRACKER_IOU_THRESHOLD` / `TRACKER_LOW_IOU` | `0.3` / `0.5` | Minimum IoU for a match in stage 1 / stage 2 |
| `TRACKER_MAX_AGE` | `10` | Sampled frames a hidden player keeps their id (10 at 5 fps = 2 s) |
| `TRACKER_MIN_HITS` | `3` | Sightings before a track is confirmed and gets a player id |
| `MIN_BOX_AREA_REL` | `0.0005` | Ignore player boxes smaller than this fraction of the frame |
| `JITTER_PX` | `2.0` | Feet movements below this (pixels) are detector wobble, not distance |
| `HEATMAP_GRID_W` / `HEATMAP_GRID_H` | `32` / `18` | Heatmap grid size |
| `POSSESSION_DIST_RATIO` | `0.5` | Ball counts as at a player's feet within this × their box height |
| `POSSESSION_MIN_FRAMES` | `3` | Sampled frames in a row before possession changes hands |
| `TEAM_MIN_SEPARATION` | `0.2` | Jersey-colour clusters closer than this → all players `unknown` team |
| `MAX_VIDEO_DURATION_SECONDS` | `60` | Maximum allowed duration for processing |
| `MAX_UPLOAD_SIZE_BYTES` | `104857600` | Maximum upload size (100 MB); enforced before and while the body is read |
| `UPLOAD_TMP_DIR` | system temp | Parent dir for per-request upload temp dirs (always removed) |
| `YTDLP_COOKIES_B64` | `""` | Optional: base64 cookies.txt (throwaway account) if YouTube blocks the server — secret |
| `YTDLP_PROXY` | `""` | Optional: proxy for yt-dlp and the media download |

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
