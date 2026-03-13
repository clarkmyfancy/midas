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
