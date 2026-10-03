---
description: Run a read-only code and security review of the current diff or a given path using the reviewer persona, with a findings table and likely reviewer questions.
---

# /review [path | --staged | --last-commit]

1. Adopt `.agent/agents/reviewer.md`. Do NOT edit files during this workflow.
2. Determine scope: default `git diff` + `git diff --cached`; or the given path; or `git show HEAD`.
3. Walk the reviewer checklist item by item. For security-sensitive files also consult skills
   `oauth-pkce-sessions`, `ssrf-safe-url-fetch`, `upload-validation`, `postgres-job-queue`.
4. Run read-only checks: design checker, `ruff check`, `grep -rn "shell=True\|os.system" backend`,
   `grep -rn "argparse\|sys.argv" backend`, and a query scan for job/video/result reads missing
   `user_id`.
5. Output the findings table + "Questions a reviewer may ask" with answers.
6. Offer: "Fix blockers now via /implement-ticket?", create follow-up tickets (T-F01…) in
   TICKETS.md under "Follow-ups" if the user agrees.
