---
description: Run the full local quality gate, backend lint, design checker, unit and integration tests, frontend lint/typecheck/build and docker build, and report a compact pass/fail table.
---

# /run-checks

1. `ruff check backend && ruff format --check backend`
2. `python -c "import sys; sys.path.insert(0,'.agent/skills/python-backend-design/scripts'); import check_design; sys.exit(check_design.main('backend/app'))"`
3. `pytest -q backend/tests -m "not integration and not model"`
4. Ensure DB is up (`docker compose up -d db`), then `pytest -q backend/tests -m integration`
5. `cd frontend && npm run lint && npm run typecheck && npm run build`
6. `docker build -t analyzer:local .` (skip if the user says it's slow; say it was skipped)
7. Report:
```
| Check | Result | Notes |
```
For failures give the first error, likely cause, and the ticket it belongs to. Do not fix in this
workflow unless the user asks.
