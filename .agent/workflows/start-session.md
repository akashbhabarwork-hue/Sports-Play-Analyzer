---
description: Start a timed work session, log start time in the README session log, show hours used and the next tickets.
---

# /start-session

1. Get time: `TZ=Asia/Kolkata date '+%Y-%m-%d %H:%M'`.
2. In `README.md` → "Session log", append a row `| n | <start> | (open) | | |`.
   If a previous row is still `(open)`, ask the user when it actually ended before continuing.
3. Sum durations of closed rows → hours used. Warn if ≥7 h (suggest cuts) or ≥9 h (stop features,
   finish docs/deploy).
4. Show the status block from skill `stage-report` (stage, done/total, next 3 tickets).
5. Ask: "Continue with T-xxx?" and wait.
