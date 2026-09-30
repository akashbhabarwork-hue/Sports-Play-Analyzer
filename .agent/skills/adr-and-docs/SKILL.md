---
name: adr-and-docs
description: Writes and maintains the submission documents — docs/ADR.md (1–2 page architecture decision record with trade-offs, cuts and future work), AI_USAGE.md (tools, key prompts, at least two cases where the AI was wrong and how they were caught), README.md (run, test, deploy, env vars, session log), .env.example and the 5-minute Loom walkthrough script. Use when creating or updating any of these files.
---

# ADR, AI usage, README, Loom

Templates in `resources/`: `ADR.template.md`, `AI_USAGE.template.md`, `README.template.md`,
`loom-script.template.md`. Copy into place at kickoff; fill progressively (after each stage),
not at the end.

## Principles
- Everything must be true and traceable: ADR decisions come from `docs/decisions.md`; AI mistakes
  come from devlog "⚠ Correction" entries; prompts are real prompts the user typed.
- ADR stays 1–2 pages: prefer tables and one Mermaid diagram over prose.
- First person, plain language — the user will be asked to defend it live.
- "What I cut" must name concrete requirements/bonuses skipped and why (time cap, risk).

## ADR must cover (reviewer checklist from the brief)
architecture + data flow · model choice (accuracy, speed, cost, licence) · queue design & index
justification · session strategy (httpOnly/Secure/SameSite cookie, why) · SSRF approach ·
YouTube datacenter blocking + upload fallback · storage · host · CI/CD + rollback path ·
tradeoffs · what was cut · what I'd do with more time.
