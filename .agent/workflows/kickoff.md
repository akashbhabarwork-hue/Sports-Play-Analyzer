---
description: One-time project kickoff, verify the agent stack, create doc skeletons, confirm open decisions with the user, and prepare stage S0.
---

# /kickoff

1. Read `.agent/rules/00-project-core.md`, `docs/TICKETS.md` and list `.agent/agents/` and
   `.agent/skills/`. Post a 5-line summary: goal, stack, stages, number of tickets, total estimate.
2. Check tooling (read-only): `git --version`, `docker --version`, `docker compose version`,
   `python3 --version`, `node --version`, `ffmpeg -version | head -1`. Report missing tools; do not
   install anything globally without asking.
3. If not a git repo, ask the user, then `git init` and create `.gitignore` (Python, Node, `.env`,
   `/data`, `*.onnx`, videos).
4. Create doc skeletons if missing (from skill `adr-and-docs/resources` and `stage-report`):
   `README.md`, `docs/ADR.md`, `AI_USAGE.md`, `docs/decisions.md` (header only),
   `docs/devlog/DEVLOG.md` (header only), `docs/acceptance.md`.
5. Present the open decisions from TICKETS.md stage S0 (T-001…T-004) as a numbered list with the
   default recommendation for each and ask the user to confirm or change. Record answers as D-001…
6. Run `/start-session` if a session isn't already open.
7. Commit: `chore: T-000 project kickoff and agent stack` (ask before committing).
8. Post: "Kickoff done. Next ticket: T-00x. Run /implement-ticket T-00x".
