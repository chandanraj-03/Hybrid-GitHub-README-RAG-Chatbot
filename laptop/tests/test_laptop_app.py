import pytest
from fastapi.testclient import TestClient
from laptop.app.main import app
from laptop.app.config import laptop_settings


@pytest.fixture
def laptop_client():
    with TestClient(app) as c:
        yield c


class TestLaptopService:

    def test_laptop_health(self, laptop_client):
        response = laptop_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "model" in data

    def test_generate_rejects_missing_or_invalid_auth(self, laptop_client):
        # No header
        resp1 = laptop_client.post("/generate", json={
            "question": "How to install?",
            "context": []
        })
        assert resp1.status_code == 401

        # Invalid token
        resp2 = laptop_client.post(
            "/generate",
            json={"question": "How to install?", "context": []},
            headers={"Authorization": "Bearer wrong-token"}
        )
        assert resp2.status_code == 401

    def test_generate_with_valid_token(self, laptop_client):
        valid_token = laptop_settings.LAPTOP_API_TOKEN
        payload = {
            "question": "How to install this project?",
            "context": [
                {
                    "text": "## Installation\n\nRun pip install myproject",
                    "section": "Installation"
                }
            ],
            "conversation": []
        }

        response = laptop_client.post(
            "/generate",
            json=payload,
            headers={"Authorization": f"Bearer {valid_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "model" in data
        assert len(data["answer"]) > 0
