---
description: End the work session, close the session log row, summarise what was done and why, make sure devlog and tickets are current, and commit.
---

# /end-session

1. Get time: `TZ=Asia/Kolkata date '+%Y-%m-%d %H:%M'`; close the open row in README session log with
   end time, duration (h m) and ticket ids done; update the running total line.
2. Make sure every ticket finished this session has a DEVLOG entry and is ticked in TICKETS.md.
   Fill any gap now.
3. If a stage was completed this session and has no stage summary, run `/stage-summary`.
4. If any "⚠ Correction" happened this session and isn't in AI_USAGE.md, add it (`/log-ai-mistake`).
5. Post the session summary in chat:
```
🕒 Session n: <start>–<end> (<dur>) · total <h>/10
Done: T-… (one line each: what + why)
Decisions: D-…
Open issues / next session starts with: T-…
```
6. `git status`; propose commit `docs: session n log and devlog` and ask before committing/pushing.
