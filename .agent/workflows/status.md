---
description: Show a compact project status — current stage, tickets done vs remaining, hours used against the 10-hour cap, risks and the next three tickets.
---

# /status

1. Parse `docs/TICKETS.md`: count `[x]` vs `[ ]` per stage and priority (MUST/SHOULD/BONUS).
2. Parse README session log for hours used (+ open session elapsed).
3. Read the last 3 DEVLOG entries for context.
4. Output the status block from skill `stage-report`. Add a risk line if: hours used > planned
   share of done estimates, any MUST ticket blocked, or deploy/YouTube spike not yet done.
