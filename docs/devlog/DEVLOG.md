# Development log

One entry per ticket, newest at the bottom. Written by the agent, reviewed by me.
Stage summaries live in `docs/devlog/stages/`.

---

## 2026-09-30 00:58 IST — T-001 Kickoff: repo scaffold and doc skeletons (agent: orchestrator)
**What changed:** Created `.gitignore`, `.env.example`, `README.md` (with session log initialized), `docs/ADR.md`, `AI_USAGE.md`, `docs/acceptance.md`, `docs/decisions.md`, and directory skeletons for `backend/`, `frontend/`, `.github/workflows/`.
**Why:** Assignment requirement §1 & §7 to establish project structure, session logging, and architecture documentation from the very first commit.
**Decisions:** D-001 through D-006 recorded in `docs/decisions.md`.
**Verification:** `git status` verifies all scaffolded paths; tooling check verified available compilers/interpreters.
**AI mistakes caught:** none.
**Explain-it-in-review:** "We set up an agentic, ticket-driven repository layout with strict separation between pure CV/domain logic, adapters, entrypoints, and frontend SPA, backed by a clear ADR and session log."
**Next:** T-002 Confirm open decisions & T-010 Backend skeleton.
