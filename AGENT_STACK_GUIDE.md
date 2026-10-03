# Agent stack guide (Google Antigravity)

## Install
Copy `.agent/` and `docs/` into the root of your (empty) project repo and open the folder in
Antigravity. Restart the agent session so rules, skills and workflows are detected.
`.agent/` is read for backward compatibility; newer Antigravity versions default to `.agents/`;
rename the folder if your version doesn't pick it up (nothing inside depends on the name except
paths like `.agent/skills/...` in rules/workflows; search-replace them if you rename).

## What's inside
| Layer | Folder | Loaded | Purpose |
|---|---|---|---|
| Rules | `.agent/rules/` | always_on / glob / model_decision | project facts, transparency, git, backend style, security, DB, CV, frontend, tests, CI/CD |
| Skills | `.agent/skills/*/SKILL.md` | on demand (by description) | deep how-tos with code: queue, OAuth, SSRF, uploads, ffmpeg, detection, tracking, metrics, UI, tests, CI/CD, deploy, docs, reporting |
| Workflows | `.agent/workflows/` | you type `/name` | kickoff, sessions, implement-ticket, stage-summary, review, checks, acceptance, status, AI-mistake log |
| Agents | `.agent/agents/` | loaded by `/implement-ticket` via the ticket's Agent field | 11 personas: orchestrator, architect, backend-api, database, auth-security, cv-pipeline, frontend, devops, qa, reviewer, docs-scribe |
| Tickets | `docs/TICKETS.md` | source of truth for work | 44 tickets in 12 stages + bonus |

## Daily loop
1. `/kickoff` (first time only)
2. `/start-session`
3. `/implement-ticket T-0xx` → approve plan → review diff → approve commit (repeat)
4. `/stage-summary` runs automatically when a stage completes
5. `/review` before merging anything risky; `/run-checks` any time
6. `/end-session`

## Where to see what the agent did and why
- Chat: Plan brief before each ticket, `▶ step, reason` narration, `⚠ Correction` notes
- `docs/devlog/DEVLOG.md`: per-ticket what/why/decisions/verification/review notes
- `docs/devlog/stages/`: per-stage summaries with diagrams and interview Q&A
- `docs/decisions.md` → promoted into `docs/ADR.md`
- `AI_USAGE.md`: every case the AI was wrong

## Recommended Antigravity settings
Terminal auto-execution: "Request Review" (you approve commands). Keep non-workspace file access off.
