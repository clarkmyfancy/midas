from fastapi.testclient import TestClient

from app.main import app
from midas.core.memory import PROJECTION_TYPES


client = TestClient(app)


def register_user(email: str) -> str:
    response = client.post(
        "/v1/auth/register",
        json={"email": email, "password": "supersecret"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_journal_ingestion_defaults_source_to_manual() -> None:
    access_token = register_user("behavior@example.com")

    response = client.post(
        "/v1/journal-entries",
        json={"journal_entry": "Default source check.", "goals": []},
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    assert response.json()["entry"]["source"] == "manual"


def test_journal_ingestion_queues_expected_projection_types() -> None:
    access_token = register_user("projection-types@example.com")

    response = client.post(
        "/v1/journal-entries",
        json={"journal_entry": "Projection types check.", "goals": []},
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    projection_types = {
        job["projection_type"] for job in response.json()["projection_jobs"]
    }
    assert projection_types == set(PROJECTION_TYPES)


def test_memory_settings_endpoint_reflects_auto_projection_flag(monkeypatch) -> None:
    monkeypatch.setenv("MIDAS_AUTO_PROJECT", "1")

    access_token = register_user("settings@example.com")
    response = client.get(
        "/v1/memory/settings",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    assert response.json() == {"auto_project_enabled": True}


def test_clarification_task_list_defaults_to_pending_items(monkeypatch) -> None:
    monkeypatch.setenv("MIDAS_AUTO_PROJECT", "0")
    access_token = register_user("clarify-behavior@example.com")

    create_response = client.post(
        "/v1/journal-entries",
        json={"journal_entry": "Josh helped after the meeting.", "goals": []},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert create_response.status_code == 200

    run_response = client.post(
        "/v1/projection-jobs/run?limit=10",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert run_response.status_code == 200

    clarifications_response = client.get(
        "/v1/clarifications",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert clarifications_response.status_code == 200
    assert clarifications_response.json()["tasks"]
    assert all(task["status"] == "pending" for task in clarifications_response.json()["tasks"])
