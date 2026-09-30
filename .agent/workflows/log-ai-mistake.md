---
description: Record a case where the AI was wrong — what it did, how it was caught, the fix and the lesson — in AI_USAGE.md and the devlog.
---

# /log-ai-mistake <short description>

1. Gather facts from the conversation, devlog and git (`git log -p` for the fix commit). Do not
   embellish; if a detail is unknown, ask the user.
2. Append to `AI_USAGE.md` → "Where the AI was wrong" using the template (What it did / How I caught
   it / Fix / Lesson), and link the commit sha and ticket id.
3. Add a one-line reference in the current DEVLOG entry.
4. Tell the user which case is the strongest candidate for the Loom "one thing the AI got wrong".
