---
name: github-actions-cicd
description: Writes GitHub Actions CI (lint, test, build on every push and PR) and CD (on merge to main, build Docker image, push to GHCR, run Alembic migrations, deploy, smoke-test /health and fail if unhealthy) with least-privilege permissions, SHA-pinned actions, GitHub Environments for secrets, concurrency control and a manual rollback workflow. Use for anything in .github/workflows.
---

# GitHub Actions CI/CD

Templates: `resources/ci.yml`, `resources/cd.yml`, `resources/rollback.yml`. Copy to
`.github/workflows/`, then **replace every `<SHA>` placeholder** with the real 40-char commit SHA:
```bash
git ls-remote https://github.com/actions/checkout 'refs/tags/v4*'   # pick tag, use the ^{} line if present
```
Keep the `# vX.Y.Z` comment next to each SHA. Never guess a SHA (a common AI error, log it if it
happens). Optionally add Dependabot for `github-actions` to keep pins fresh.

## Requirements checklist (the reviewers read the YAML)
- [ ] CI on `push` + `pull_request`: ruff, pytest unit, pytest integration (postgres service),
      frontend lint/typecheck/build, docker build (no push).
- [ ] CD only on `push` to `main` (merge), `environment: production`.
- [ ] Steps in order: build → push GHCR → migrate → deploy → smoke `/health` (fails if unhealthy).
- [ ] Top-level `permissions: {}`; per job minimal (`contents: read`; `packages: write` only on the
      push job).
- [ ] All actions pinned by SHA.
- [ ] `concurrency: { group: deploy-production, cancel-in-progress: false }` for CD.
- [ ] Secrets only from the `production` environment: `DATABASE_URL`, `FLY_API_TOKEN`, app secrets
      live in the host (`fly secrets set`), not in the workflow.
- [ ] Image tags: `ghcr.io/<owner>/<repo>:<git-sha>` (immutable) and `:main`.

## Migrations step
Runs the just-built image against the prod DB (DB must be reachable from GitHub runners, e.g.
Neon over TLS). Alembic migrations must be backward compatible with the currently running image
(expand/contract), because the migration runs *before* the new code is live.
