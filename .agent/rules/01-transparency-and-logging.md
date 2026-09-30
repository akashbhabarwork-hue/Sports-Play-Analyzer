---
trigger: always_on
---

# Transparency: always tell the user WHAT you are doing and WHY

The user must understand and defend every line in a live review. Optimise for their
understanding, not just speed.

## Before touching files (every task)
Post a short **Plan brief** in chat (under ~12 lines):
```
🎯 Ticket: T-xxx <title>   🤖 Agent: <persona from .agent/agents>
What: <1–2 lines>
Why: <requirement it satisfies — quote the assignment bullet if possible>
Files: <create/modify list>
Approach: <key technique, e.g. "FOR UPDATE SKIP LOCKED claim + lease">
Risks / alternatives considered: <1–2 lines>
Verify by: <exact commands / tests>
```
Use Antigravity's Implementation Plan artifact for anything touching >3 files. Wait for user
approval before executing when the ticket is tagged `[review-plan]` or touches auth, security,
migrations or CI/CD.

## While working
- Narrate each meaningful step in one line: `▶ step — reason`. Don't dump big code blocks into
  chat; the diff is the code.
- When choosing between options, state which and why in one sentence and append it to
  `docs/decisions.md` (format below).
- If you discover you were wrong (bad API, hallucinated flag, a failing test caused by your code),
  say so plainly: `⚠ Correction: I assumed X, actually Y, caught by Z.` and append it to
  `AI_USAGE.md` → "Where the AI was wrong". Never hide or silently rewrite a mistake.

## After finishing a ticket
1. Run the ticket's verification commands and report the result (pass/fail counts).
2. Append to `docs/devlog/DEVLOG.md`:
```
## <YYYY-MM-DD HH:MM IST> — T-xxx <title>  (agent: <persona>)
**What changed:** files + purpose
**Why:** requirement / reasoning
**Decisions:** chosen vs rejected (link D-xxx)
**Verification:** commands + result
**AI mistakes caught:** none | description
**Explain-it-in-review:** 2–3 lines the user can say in the interview
**Next:** next ticket id
```
3. Tick the ticket in `docs/TICKETS.md` (`[ ]` → `[x]`) and fill its "Done notes".
4. Propose a commit (see git rule). Show the message; the user approves.

## After finishing a stage (all tickets of stage S-xx done)
Run `/stage-summary`: write `docs/devlog/stages/Sxx-<name>.md` using the `stage-report` skill
template, then post a 5–8 line summary in chat.

## decisions.md entry format
```
### D-xxx <title> (<date>, T-xxx)
Context: … | Options: A / B / C | Chosen: B | Because: … | Consequences: …
```
Decisions reviewers care about (model, session strategy, queue, host, SSRF, rollback, YouTube
blocking, what was cut) are promoted into `docs/ADR.md` by the docs agent.

## Tone
Plain English, short sentences, no hype. Explain jargon the first time it appears
(e.g. "PKCE — a one-time secret proving the client that started login is the one finishing it").
