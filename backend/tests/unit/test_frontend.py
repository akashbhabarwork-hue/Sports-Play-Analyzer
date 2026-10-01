from fastapi.testclient import TestClient

from app.config import Settings
from app.entrypoints.api import create_app
from app.wiring import Container


class FakeHealthCheck:
    def check_db(self) -> bool:
        return True


def make_client(static_dir: str) -> TestClient:
    settings = Settings(
        app_env="test",
        app_origin="http://test",
        database_url="sqlite:///:memory:",
        git_sha="test_sha",
        static_dir=static_dir,
    )
    return TestClient(create_app(Container(settings=settings, health_check=FakeHealthCheck())))


def test_frontend_spa_fallback(tmp_path):
    (tmp_path / "index.html").write_text('<div id="root"></div>')
    client = make_client(str(tmp_path))

    response = client.get("/random-react-route")
    assert response.status_code == 200
    assert 'id="root"' in response.text


def test_frontend_spa_does_not_shadow_api(tmp_path):
    (tmp_path / "index.html").write_text('<div id="root"></div>')
    client = make_client(str(tmp_path))

    assert client.get("/api/unknown").status_code == 404


def test_no_static_dir_means_no_spa_route(tmp_path):
    client = make_client(str(tmp_path / "missing"))

    assert client.get("/random-react-route").status_code == 404
