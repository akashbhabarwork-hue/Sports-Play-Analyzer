---
name: stage-report
description: Produces human-readable progress reporting, per-ticket devlog entries, per-stage summary documents with data flow, decisions, demo steps, known gaps and likely interview questions, and short chat status reports. Use when a ticket or stage completes, when the user asks "what did you do / why / where are we", or at session end.
---

# Stage & progress reporting

Goal: the user can read `docs/devlog/` alone and explain the whole build in an interview.

## Per ticket → append to `docs/devlog/DEVLOG.md`
Use the entry format in rule `01-transparency-and-logging`.

## Per stage → `docs/devlog/stages/Sxx-<slug>.md`
Use `resources/stage-template.md`. Fill from the devlog entries of that stage + git log:
`git log --oneline --since="<stage start>"`. Keep it to about one page.

## Status report (on request or `/status`)
```
📍 Stage S-xx <name>, n/m tickets done   ⏱ hours used: X.X / 10
✅ Done since last report: T-…, T-…
🔨 In progress: T-… (what's left)
⛔ Blocked/risks: …
➡️ Next 3: T-…, T-…, T-…
🧪 Tests: unit X pass · integration Y pass
```
Hours come from the README session log (+ current session elapsed).

## Style
Concrete over vague ("claim query uses partial index ix_jobs_claimable" not "improved DB").
Every "why" ties back to an assignment bullet or a decision id.
