# AI Usage

## Tools used
| Tool | Used for |
|---|---|
| Google Antigravity (agent: Gemini 3.7 Flash) | Architecture planning, scaffolding, ticket-driven implementation, tests, and security review |
| Claude / Gemini Code Assist | Auxiliary code verification & test coverage analysis |

Setup: project rules, specialist agent personas, skills and workflows in `.agent/` (personas per area, ticket-driven, every change logged in `docs/devlog/`).

## Key prompts
1. `/kickoff` — Scaffolding project layout, doc skeletons, tooling audit, and initial decision logs.
2. `/implement-ticket T-xxx` — Specialist agent persona execution with plan brief, atomic implementation, test verification, and devlog logging.

## Where the AI was wrong (and how I caught it)
*(Running log of mistakes caught during development — will be updated as tickets are implemented)*

### 1. Explicit Protocol Inheritance
- **What it did:** The agent explicitly inherited from a `typing.Protocol` (`class PostgresHealthCheck(HealthCheck):`).
- **How I caught it:** Running the python backend design checker script (`check_design.py`) caught it as a `[no-inheritance]` violation.
- **Fix:** Removed the explicit inheritance, relying on Python's implicit duck-typing composition for Protocols.
- **Lesson:** `typing.Protocol` is structurally typed and does not require explicit inheritance unless specifically needed at runtime.

### 2. `*.ts` in .gitignore swallowed TypeScript sources
- **What it did:** During kickoff the agent added `*.ts` to `.gitignore` as a video extension. T-011's `vite.config.ts`, `src/vite-env.d.ts` and `src/api.ts` were therefore never committed, yet the ticket was marked done because the checks passed on the local working copy.
- **How I caught it:** Preparing CI (T-013) on a fresh clone: `npm run typecheck` failed with `Cannot find module './index.css'` and `No inputs were found ... vite.config.ts`; `git check-ignore -v` pointed at the rule.
- **Fix:** Replaced `*.ts` with `*.m2ts`/`*.mts`, recreated the three files, and CI now builds from a clean checkout.
- **Lesson:** Verify on a fresh clone (CI), not the working copy; never ignore a wildcard that collides with a source-code extension.

### 3. Entrypoint target that did not exist, and a typecheck that checked nothing
- **What it did:** T-012 used `uvicorn app.entrypoints.api:app` in the Dockerfile and compose, but `api.py` only defines `create_app()`; T-011's `typecheck` script ran `tsc --noEmit` against a root tsconfig with `files: []`, which checks zero files.
- **How I caught it:** Reviewing the T-012/T-011 outputs while writing CI (Docker was never run locally); proved the typecheck gap by adding a deliberately wrong file and seeing it pass.
- **Fix:** `uvicorn --factory app.entrypoints.api:create_app`; `typecheck` is now `tsc -b`; CI's docker job runs the built image and smoke-tests `/health`.
- **Lesson:** A "skipped verification" note is a debt — add an automated check that would have failed.

## How I verified AI-generated code
- Automated unit test suite with deterministic JSON fixtures (pure logic, no model dependency).
- Integration tests against migrated Postgres schema with multi-user isolation checks.
- Read-only `/review` passes checking for secrets, injection vulnerabilities, and proper error handling.
- Reviewer persona verification and live acceptance check scenario runs (`/acceptance-check`).
