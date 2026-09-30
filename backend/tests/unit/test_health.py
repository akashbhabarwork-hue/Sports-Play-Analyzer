from fastapi.testclient import TestClient
from app.entrypoints.api import create_app
from app.wiring import Container
from app.config import Settings
from app.core.ports import HealthCheck

class FakeHealthCheck(HealthCheck):
    def __init__(self, is_ok: bool):
        self.is_ok = is_ok
        
    def check_db(self) -> bool:
        return self.is_ok

def test_health_ok():
    settings = Settings(
        app_env="test",
        app_origin="http://test",
        database_url="sqlite:///:memory:",
        git_sha="test_sha"
    )
    container = Container(settings=settings, health_check=FakeHealthCheck(True))
    app = create_app(container)
    client = TestClient(app)
    
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok", "version": "test_sha"}

def test_health_db_down():
    settings = Settings(
        app_env="test",
        app_origin="http://test",
        database_url="sqlite:///:memory:",
        git_sha="test_sha"
    )
    container = Container(settings=settings, health_check=FakeHealthCheck(False))
    app = create_app(container)
    client = TestClient(app)
    
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json() == {"status": "error", "db": "error", "version": "test_sha"}
