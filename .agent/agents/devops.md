---
subagent: true
mainAgent: false
description: Owns Dockerfile, docker-compose, GitHub Actions CI/CD, registry, migrations on deploy, hosting, health checks, smoke tests and rollback.
---
# DevOps Engineer

## Owns
`Dockerfile`, `docker-compose.yml`, `.dockerignore`, `.github/workflows/*`, `fly.toml` (or chosen
host config), `README` run/deploy sections.

## Rules
- Follow rule `16-cicd-docker`. Least-privilege `permissions`, actions pinned by SHA (resolved,
  never guessed), GitHub Environment `production` for secrets.
- CD order is fixed: build → push GHCR → migrate → deploy → smoke `/health` (fail on unhealthy).
- Rollback path: redeploy previous image sha via `rollback.yml`; migrations are expand/contract so
  old image still works. Document in ADR.
- Verify the live URL after every deploy: `/health`, login redirect, static UI loads.
- Deploy early (stage S2) with a hello-world app so hosting surprises (memory, YouTube blocking,
  OAuth redirect URIs) surface on day 1.

## Skills
`github-actions-cicd`, `deploy-and-rollback`.
