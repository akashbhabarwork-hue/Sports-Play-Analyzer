---
description: Implement one ticket end-to-end with the right specialist persona, plan brief, build, test, devlog, tick ticket, commit. Usage /implement-ticket T-012
---

# /implement-ticket <T-id>

1. **Load the ticket** from `docs/TICKETS.md` (the id is in the user's message; if missing, pick the
   next unblocked MUST ticket and say which). Check `Depends on` are all `[x]`; if not, stop and say
   what's blocking.
2. **Switch persona**: read `.agent/agents/<Agent field>.md`, announce
   `🤖 <agent> takes T-xxx, <why this persona>`. Read the skills that persona lists that are relevant.
3. **Plan brief** (rule 01 format). If the ticket is tagged `[review-plan]` or touches auth,
   security, migrations or `.github/`, create an Implementation Plan artifact and WAIT for approval.
4. **Tests first where the ticket has pure logic**: write/extend unit tests from the acceptance
   criteria, run them, show they fail for the right reason.
5. **Implement** in small steps, narrating `▶ step, reason`. Stay inside the ticket scope; note
   anything out-of-scope as a proposed new ticket instead of doing it.
6. **Verify**: run the ticket's "Verify" commands plus rule-required checks (ruff, design checker,
   unit tests; frontend lint/typecheck/build when relevant). Fix failures (max 2 attempts, then
   stop and report root cause + options).
7. **Self-review** against `.agent/agents/reviewer.md` checklist (quick pass, list findings, fix
   blockers).
8. **Record**: DEVLOG entry, decisions.md for any choice made, AI_USAGE.md for any correction,
   tick the ticket + "Done notes".
9. **Commit** proposal: `<type>(<scope>): T-xxx <summary>`; show `git diff --stat`; ask before commit.
10. If this ticket completes its stage → run `/stage-summary`. Then print:
    `✅ T-xxx done · tests: … · next: T-yyy (<agent>)`.
