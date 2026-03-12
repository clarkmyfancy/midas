from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_healthcheck() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_reflection_endpoint() -> None:
    response = client.post(
        "/v1/reflections",
        json={
            "journal_entry": "I felt tired after work, but I still went for a walk.",
            "goals": ["Protect energy", "Stay active"],
        },
    )

    body = response.json()

    assert response.status_code == 200
    assert "summary" in body
    assert len(body["findings"]) >= 2
    assert any("habit_analyst" in item for item in body["trace"])

