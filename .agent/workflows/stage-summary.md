---
description: Write the stage summary document for a completed stage (what was built, data flow, decisions, demo steps, gaps, interview Q&A) and post a short chat summary.
---

# /stage-summary [S-xx]

1. Identify the stage (argument, or the stage of the last completed ticket). Confirm all its MUST
   tickets are `[x]`; list any skipped SHOULD/BONUS items.
2. Collect inputs: DEVLOG entries for the stage's tickets, `docs/decisions.md` entries, and
   `git log --oneline` for the stage's commits.
3. Create `docs/devlog/stages/Sxx-<slug>.md` from `.agent/skills/stage-report/resources/stage-template.md`.
   Include a Mermaid diagram of the data flow as it exists now and 3–5 likely interview questions
   with short, correct answers grounded in the actual code (cite file paths).
4. Promote reviewer-relevant decisions into `docs/ADR.md` (keep it ≤2 pages).
5. Post in chat (≤8 lines): what the stage delivered, why it matters for acceptance, how to demo it,
   known gaps, next stage.
6. Propose commit `docs: S-xx stage summary`.
