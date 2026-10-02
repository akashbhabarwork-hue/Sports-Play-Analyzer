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

### 4. A test that could not fail
- **What it did:** The first atomicity test for `create_with_video` passed `config=None` to force the job insert to fail, assuming a NOT NULL violation. SQLAlchemy serialises `None` to JSON `null`, so the insert succeeded and the "test" asserted nothing useful.
- **How I caught it:** The test failed for the wrong reason (no exception), and the next attempt raised a Python `TypeError` instead of a database error.
- **Fix:** Use a value Postgres rejects (`\u0000` in jsonb), then temporarily split the method into two transactions to confirm the test goes red (orphan video row).
- **Lesson:** Mutation-check new safety tests: break the code on purpose and watch the test fail.

### 5. Following its own spec too literally
- **What it did:** The metrics skill (written by the agent at kickoff) said to skip feet movements under `JITTER_PX` and to cluster teams on hue + saturation. Implemented literally, a player walking 1 px per sampled frame covers zero distance, white and black kits (both unsaturated) look identical, and red shirts at hue 359° and 1° land in different teams.
- **How I caught it:** Writing edge-case tests before trusting the formulas (slow walker, white-vs-black, red wrap-around), then mutation runs to check each test could fail.
- **Fix:** Distance measured from the last counted position with a dead-band; colour feature `(s·cos h, s·sin h, v)` with medians (D-022, D-023).
- **Lesson:** A spec written by the same assistant isn't a source of truth; test its edge cases like any other code.

### 6. Banker's rounding and a Windows-only pipe error
- **What it did:** (a) In T-060 the agent wrote a test expecting 641×361 to round *up* to 642×362, then implemented it with Python's `round()`, which rounds halves to even (361/2 = 180.5 → 180). (b) Its first encoder only caught `BrokenPipeError` when ffmpeg dies mid-stream; on Windows the same failure is `OSError(EINVAL)`.
- **How I caught it:** (a) The test went red on the first run. (b) Self-review against the reviewer checklist, then a new test (`test_encoder_reports_ffmpeg_dying_mid_stream`) that points ffmpeg at an unwritable path.
- **Fix:** Floor to even (output is never larger than the source); catch `OSError`, the parent of `BrokenPipeError`.
- **Lesson:** Platform and rounding semantics are easy to "know" wrongly; pin them with a test.

### 7. Config docs that drifted from the code
- **What it did:** In T-060 the agent appended a new `SAMPLE_FPS=5` block to `.env.example` without noticing the variable was already there, and didn't add its new variables to the README env table. `.env.example` also still listed `CONF_THRESHOLD`, which no code reads.
- **How I caught it:** Reading `.env.example` in full while adding the T-061 detector settings.
- **Fix:** One detector/video section in `.env.example`, README rows for every new variable, `CONF_THRESHOLD` removed (players use `TRACKER_LOW_THRESH`, the ball `BALL_CONF_THRESHOLD`).
- **Lesson:** When adding a setting, grep for the name in `.env.example` and README first; tests don't check docs.

### 8. Two test files with the same name
- **What it did:** In T-062 the agent created `tests/unit/test_process_job.py` and `tests/integration/test_process_job.py`. The test folders have no `__init__.py`, so pytest imports test modules by bare file name and the second one failed to collect ("import file mismatch").
- **How I caught it:** Running both files together before committing.
- **Fix:** Renamed the Postgres one to `test_process_job_pg.py` (the ticket's `-k process_job` still selects it); shared clip builders and the scripted detector moved to `tests/pipeline_helpers.py`.
- **Lesson:** Check the repo's test-module conventions (existing names are unique across folders for this reason).

### 9. A worker that a database blip would kill
- **What it did:** In T-063 the agent's first `run_once` guarded `process_job` with a broad `except`, but left `sweep_dead()` and `claim()` outside it. A short Postgres outage would have raised out of the loop and ended the worker process — and the compose service had no restart policy — so queued jobs would sit until someone noticed.
- **How I caught it:** Self-review question "what happens if the database is down while the worker is idle?", then two failing regression tests (`DownQueue`, `FlakyQueue`).
- **Fix:** `ExternalServiceError` from the poll is logged and treated as an idle poll; compose `restart: unless-stopped` as a second safety net.
- **Lesson:** For long-running loops, test the failure of every call in the loop, not just the main work.

### 10. A commit silently missing a folder, and wrong advice about `.claude/`
- **What it did:** (a) In T-080 the agent put the frontend's pure helpers in `frontend/src/lib/`. The repo's Python-template `.gitignore` ignores every `lib/` directory, so `git add` skipped it with only a hint, and the first T-080 commit imported a file that wasn't in the commit — CI would have failed on a clean checkout. (b) Earlier the agent told the owner to stop ignoring `.claude/`; checking `git ls-files` later showed the repo deliberately tracks `.agent/` and keeps `.claude/` local, so that advice (and the owner's local CI path edit it encouraged) would have broken CI.
- **How I caught it:** (a) Reading `git add` output before pushing (the commit was still local); (b) `git ls-files .claude` / `.agent` while planning the CI change.
- **Fix:** Renamed to `src/logic/` and amended the unpushed commit; CI change staged on top of the committed `ci.yml` only, leaving the owner's local edit out.
- **Lesson:** After every commit, compare `git show --stat` with the files you meant to add; check what the repo actually tracks before giving advice about `.gitignore`.

## How I verified AI-generated code
- Automated unit test suite with deterministic JSON fixtures (pure logic, no model dependency).
- Integration tests against migrated Postgres schema with multi-user isolation checks.
- Read-only `/review` passes checking for secrets, injection vulnerabilities, and proper error handling.
- Reviewer persona verification and live acceptance check scenario runs (`/acceptance-check`).
