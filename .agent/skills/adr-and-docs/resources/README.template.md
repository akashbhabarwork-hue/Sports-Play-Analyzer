# Sports Play Analyzer

Upload a ≤60 s football/basketball clip or paste a YouTube link → player tracking, distance,
heatmaps, possession and an annotated video.

**Live:** <url>  ·  **ADR:** docs/ADR.md  ·  **AI usage:** AI_USAGE.md

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
Merging to `main` runs `.github/workflows/cd.yml`: build → GHCR → migrate → deploy → /health smoke.
Rollback: Actions → Rollback → enter previous sha. First-time setup: see docs/ADR.md §6.

## Configuration
| Variable | Default | Meaning |
|---|---|---|

## API
`POST /api/jobs/upload`, `POST /api/jobs/url`, `GET /api/jobs`, `GET /api/jobs/{id}`,
`GET /api/jobs/{id}/stats`, `GET /api/jobs/{id}/players/{pid}`, `GET /api/jobs/{id}/video`, `GET /health`

## Session log
| # | Start (IST) | End (IST) | Duration | What I did |
|---|---|---|---|---|

Total: 0 h 00 m
