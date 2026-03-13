from fastapi.testclient import TestClient

from app.main import app
from midas.core.loader import load_capabilities


client = TestClient(app)


def test_healthcheck() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_reflection_endpoint() -> None:
    with client.stream(
        "POST",
        "/v1/reflections",
        json={
            "journal_entry": "I felt tired after work, but I still went for a walk.",
            "goals": ["Protect energy", "Stay active"],
            "steps": 6840,
            "sleep_hours": 6.5,
            "hrv_ms": 42.0,
        },
    ) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "data: Analyzing " in body
    assert "data: Midas " in body


def test_capabilities_endpoint_defaults_to_core_mode() -> None:
    response = client.get("/v1/capabilities")

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
