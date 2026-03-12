from fastapi.testclient import TestClient

from app.main import app
from midas.core.loader import load_capabilities


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


def test_capabilities_endpoint_defaults_to_core_mode() -> None:
    response = client.get("/api/v1/capabilities")

    assert response.status_code == 200
    assert response.json() == {
        "capabilities": {
            "mental_model_graph": False,
            "pro_analytics": False,
            "weekly_reflection": False,
        }
    }


def test_pro_route_requires_installed_capability() -> None:
    load_capabilities(force=True)
    response = client.get(
        "/api/v1/pro/analytics",
        headers={"X-User-Id": "pro-user", "X-Entitlements": "pro_analytics"},
    )

    assert response.status_code == 503
