from fastapi.testclient import TestClient

from app.main import app
from midas.core.loader import load_capabilities


client = TestClient(app)


def register_and_login() -> str:
    response = client.post(
        "/v1/auth/register",
        json={"email": "user@example.com", "password": "supersecret"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_healthcheck() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_auth_register_and_login() -> None:
    register_response = client.post(
        "/v1/auth/register",
        json={"email": "user@example.com", "password": "supersecret"},
    )

    assert register_response.status_code == 200
    assert register_response.json()["token_type"] == "bearer"

    login_response = client.post(
        "/v1/auth/login",
        json={"email": "user@example.com", "password": "supersecret"},
    )

    assert login_response.status_code == 200
    assert login_response.json()["user"]["email"] == "user@example.com"


def test_reflection_endpoint() -> None:
    access_token = register_and_login()

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
        headers={"Authorization": f"Bearer {access_token}"},
    ) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "data: - Semantic drift:" in body
    assert "data: - HRV and sleep suggest strain" in body


def test_reflection_endpoint_requires_bearer_token() -> None:
    response = client.post(
        "/v1/reflections",
        json={"journal_entry": "No auth", "goals": []},
    )

    assert response.status_code == 401


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
    access_token = register_and_login()
    response = client.get(
        "/api/v1/pro/analytics",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code in {403, 503}
