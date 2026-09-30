from fastapi.testclient import TestClient
from app.entrypoints.api import create_app
import pytest

def test_frontend_spa():
    app = create_app()
    client = TestClient(app)
    
    response = client.get("/random-react-route")
    assert response.status_code == 200
    assert "id=\"root\"" in response.text or "Sports Play Analyzer" in response.text
