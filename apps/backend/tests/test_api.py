from fastapi.testclient import TestClient

from app.main import app
from midas.core.loader import load_capabilities
from midas.core.projections import GraphUserCleanupResult, WeaviateCleanupResult


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


def test_auth_me_returns_current_user() -> None:
    access_token = register_and_login()
    response = client.get(
        "/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == "user@example.com"


def test_auth_delete_data_clears_account_data_but_keeps_account(monkeypatch) -> None:
    owner_token = register_and_login()
    viewer_token = client.post(
        "/v1/auth/register",
        json={"email": "second@example.com", "password": "supersecret"},
    ).json()["access_token"]

    owner_first_entry = client.post(
        "/v1/journal-entries",
        json={"journal_entry": "Owner entry one.", "goals": []},
        headers={"Authorization": f"Bearer {owner_token}"},
    ).json()["entry"]["id"]
    owner_second_entry = client.post(
        "/v1/journal-entries",
        json={"journal_entry": "Owner entry two.", "goals": []},
        headers={"Authorization": f"Bearer {owner_token}"},
    ).json()["entry"]["id"]
    client.post(
        "/v1/journal-entries",
        json={"journal_entry": "Viewer entry.", "goals": []},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    monkeypatch.setattr(
        "app.main.WeaviateProjector.delete_objects",
        lambda self, object_ids: WeaviateCleanupResult(deleted_object_ids=list(object_ids)),
    )
    monkeypatch.setattr(
        "app.main.GraphProjector.delete_user_data",
        lambda self, user_id: GraphUserCleanupResult(
            deleted_observations=2,
            deleted_entities=5,
            deleted_relationships=7,
        ),
    )

    delete_response = client.delete(
        "/v1/auth/data",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    owner_entries_response = client.get(
        "/v1/journal-entries",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    owner_me_response = client.get(
        "/v1/auth/me",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    viewer_entries_response = client.get(
        "/v1/journal-entries",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    assert delete_response.status_code == 200
    payload = delete_response.json()
    cleanup_by_store = {item["store"]: item for item in payload["cleanup"]}
    assert cleanup_by_store["postgres"]["success"] is True
    assert cleanup_by_store["postgres"]["details"] == {
        "deleted_alias_resolution_count": 0,
        "deleted_clarification_task_count": 0,
        "deleted_entry_count": 2,
        "deleted_projection_job_count": 6,
    }
    assert cleanup_by_store["postgres"]["deleted_ids"] == [owner_second_entry, owner_first_entry]
    assert cleanup_by_store["weaviate"]["deleted_count"] == 6
    assert cleanup_by_store["neo4j"]["details"] == {
        "deleted_entity_count": 5,
        "deleted_observation_count": 2,
        "deleted_relationship_count": 7,
    }
    assert owner_entries_response.json()["entries"] == []
    assert owner_me_response.status_code == 200
    assert owner_me_response.json()["email"] == "user@example.com"
    assert [entry["journal_entry"] for entry in viewer_entries_response.json()["entries"]] == ["Viewer entry."]


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
    assert "data: - You describe pushing through strain instead of naming it directly." in body
    assert "data: - Work pressure seems to be crowding out recovery." in body


def test_reflection_endpoint_api_alias() -> None:
    access_token = register_and_login()

    with client.stream(
        "POST",
        "/api/v1/reflections",
        json={
            "journal_entry": "I dragged through the afternoon but said I was productive.",
            "goals": ["Protect focus"],
        },
        headers={"Authorization": f"Bearer {access_token}"},
    ) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "data: - You describe pushing through strain instead of naming it directly." in body


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
