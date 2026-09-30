---
trigger: always_on
---

# Git, session log and safety

## Commits (reviewers inspect history)
- Commit after every ticket (or smaller). Never batch many tickets into one commit.
- Conventional commits with ticket id: `feat(worker): T-031 claim jobs with SKIP LOCKED`.
  Types: feat, fix, test, docs, chore, ci, refactor, sec.
- Before committing: `git status`, the ticket's tests, and a secret scan
  (`git diff --cached | grep -Ei "(secret|password|token|api_key|BEGIN .*PRIVATE)"`, review hits).
- Never commit `.env`, cookie files, model weights > 50 MB, videos, `node_modules`, caches.
- Never force-push main, never rewrite published history, never skip hooks.
- Ask the user before `git push`.

## Session log (assignment requirement: README.md → "Session log")
- `/start-session` adds a row with the real start time (`TZ=Asia/Kolkata date '+%Y-%m-%d %H:%M'`).
- `/end-session` fills end time, duration and ticket ids done.
- Keep a running total; warn at 7 h and 9 h of the ≈10 h cap.
```
| # | Start (IST) | End (IST) | Duration | What I did |
|---|---|---|---|---|
```

## Terminal safety
- Prefer read-only commands for discovery. Ask before: global installs, deleting outside the repo,
  `docker system prune`, dropping databases, anything touching production.
- Never echo env vars that hold secrets. `.env` is local only; `.env.example` holds placeholders.
- Never paste real OAuth secrets, DB URLs or cookies into chat, code, tests or logs.

## Asking vs acting
Act without asking: code inside the current ticket's scope, tests, docs updates.
Ask first: scope changes, dependencies outside the locked stack, edits to an already-applied
migration, anything in `.github/`, deploys, cost-incurring cloud changes, and any deviation from
`00-project-core.md`.
