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

## How I verified AI-generated code
- Automated unit test suite with deterministic JSON fixtures (pure logic, no model dependency).
- Integration tests against migrated Postgres schema with multi-user isolation checks.
- Read-only `/review` passes checking for secrets, injection vulnerabilities, and proper error handling.
- Reviewer persona verification and live acceptance check scenario runs (`/acceptance-check`).
