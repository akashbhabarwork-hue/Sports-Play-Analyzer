---
name: testing-strategy
description: Sets up and writes pytest suites for the analyzer, pure unit tests for tracking/metrics/validation with JSON fixture detections, Postgres integration tests with Alembic-migrated schema and per-test cleanup, FastAPI TestClient with session helpers, the required user-A-vs-user-B authorization test, worker idempotency and SKIP LOCKED concurrency tests. Use when writing or running tests or CI test jobs.
---

# Testing strategy

## Layout
```
backend/tests/
  conftest.py                # settings fixture, db fixture, client fixture, make_user/login helpers
  fixtures/                  # tracks_*.json, detections_clip.json, corrupt.mp4, fake.mp4
  unit/                      # no DB/network/model/ffmpeg
  integration/               # Postgres (+ ffmpeg where marked)
```
Markers in `pyproject.toml`: `integration`, `ffmpeg`, `model`. CI unit job runs
`-m "not integration and not model"`; integration job runs `-m "integration"` with a postgres
service and ffmpeg installed.

## Fixtures (sketch)
```python
@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings(... database_url=os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://app:app@localhost:5432/app_test"),
                    cookie_secure=False, max_upload_mb=5, ...)   # built directly; no env magic

@pytest.fixture(scope="session")
def migrated_db(settings):   # run alembic upgrade head once (programmatic alembic.command.upgrade)
    ...

@pytest.fixture
def container(settings, migrated_db):
    c = build_container(settings, detector=FakeDetector.from_file(FIX / "detections_clip.json"))
    yield c
    truncate_all(c.engine)   # TRUNCATE users, jobs, ... RESTART IDENTITY CASCADE

@pytest.fixture
def client(container):
    app = create_app(container)     # api.py exposes create_app(container) for tests
    return TestClient(app)

def login_as(client, container, email) -> User:
    user = container.user_repo.upsert("google", f"sub-{email}", email, email)
    token = create_session(container.session_repo, user.id, now=container.clock.now())
    client.cookies.set(container.settings.cookie_name, token)
    return user
```
Use two separate `TestClient` instances for user A and B (separate cookie jars).

## Required authorization test
```python
@pytest.mark.integration
def test_user_b_cannot_access_user_a_job(container, settings):
    a, b = TestClient(create_app(container)), TestClient(create_app(container))
    login_as(a, container, "a@example.com"); login_as(b, container, "b@example.com")
    job_id = seed_succeeded_job(container, owner_email="a@example.com")   # direct repo inserts
    for path in [f"/api/jobs/{job_id}", f"/api/jobs/{job_id}/stats",
                 f"/api/jobs/{job_id}/players/1", f"/api/jobs/{job_id}/video",
                 f"/api/jobs/{job_id}/heatmap?team=all"]:
        assert b.get(path).status_code == 404, path
        assert a.get(path).status_code in (200, 302), path
    assert all(j["id"] != str(job_id) for j in b.get("/api/jobs").json()["jobs"])
```

## Required integration test (end-to-end without a model)
Submit `tiny.mp4` via API as user A → run one worker iteration (`run_once(container)`) with
FakeDetector → job `succeeded`, stats JSON matches schema, annotated key exists in blob store.

## Idempotency / crash tests
- Claim, then simulate crash (no finish), set lease in the past → `run_once` reclaims → succeeded;
  `SELECT count(*) FROM player_tracks WHERE job_id` equals single-run count.
- Two threads calling `claim()` simultaneously on 1 queued job → exactly one gets it.
- attempts exhausted → failed/WORKER_CRASHED.

## Writing good tests
Arrange–Act–Assert, one behaviour per test, behaviour names, no sleeps (inject a fake Clock),
deterministic seeds, fixture files small and human-readable.
