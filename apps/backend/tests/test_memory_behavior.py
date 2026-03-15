from fastapi.testclient import TestClient

from app.main import app
from midas.core.memory import (
    PROJECTION_TYPES,
    WEAVIATE_PROJECTION_TYPES,
)


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
    assert response.json() == {
        "auto_project_enabled": True,
        "auto_project_weaviate_enabled": True,
        "auto_project_neo4j_enabled": True,
    }


def test_memory_settings_endpoint_reflects_split_projection_flags(monkeypatch) -> None:
    monkeypatch.setenv("MIDAS_AUTO_PROJECT", "0")
    monkeypatch.setenv("MIDAS_AUTO_PROJECT_WEAVIATE", "1")
    monkeypatch.setenv("MIDAS_AUTO_PROJECT_NEO4J", "0")

    access_token = register_user("split-settings@example.com")
    response = client.get(
        "/v1/memory/settings",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "auto_project_enabled": True,
        "auto_project_weaviate_enabled": True,
        "auto_project_neo4j_enabled": False,
    }


def test_reflection_auto_projection_respects_split_flags(monkeypatch) -> None:
    monkeypatch.setenv("MIDAS_AUTO_PROJECT", "0")
    monkeypatch.setenv("MIDAS_AUTO_PROJECT_WEAVIATE", "1")
    monkeypatch.setenv("MIDAS_AUTO_PROJECT_NEO4J", "0")

    captured: dict[str, object] = {}

    def fake_process_pending_projection_jobs(*, limit: int, user_id: str | None = None, projection_types=None):
        captured["limit"] = limit
        captured["user_id"] = user_id
        captured["projection_types"] = projection_types

        class Result:
            claimed_jobs = 0
            completed_jobs = 0
            failed_jobs = 0
            jobs = []

        return Result()

    monkeypatch.setattr("app.main.process_pending_projection_jobs", fake_process_pending_projection_jobs)

    access_token = register_user("split-reflection@example.com")

    with client.stream(
        "POST",
        "/v1/reflections",
        json={"journal_entry": "Split projection test.", "goals": [], "thread_id": "split-projection"},
        headers={"Authorization": f"Bearer {access_token}"},
    ) as response:
        _ = "".join(response.iter_text())

    assert response.status_code == 200
    assert captured["limit"] == 10
    assert captured["user_id"]
    assert captured["projection_types"] == WEAVIATE_PROJECTION_TYPES


def test_manual_projection_run_ignores_split_auto_projection_flags(monkeypatch) -> None:
    monkeypatch.setenv("MIDAS_AUTO_PROJECT", "0")
    monkeypatch.setenv("MIDAS_AUTO_PROJECT_WEAVIATE", "0")
    monkeypatch.setenv("MIDAS_AUTO_PROJECT_NEO4J", "0")

    access_token = register_user("manual-run@example.com")

    create_response = client.post(
        "/v1/journal-entries",
        json={"journal_entry": "Manual run still sees all jobs.", "goals": []},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert create_response.status_code == 200
    assert {job["projection_type"] for job in create_response.json()["projection_jobs"]} == set(PROJECTION_TYPES)

    run_response = client.post(
        "/v1/projection-jobs/run?limit=10",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert run_response.status_code == 200
    assert {job["projection_type"] for job in run_response.json()["jobs"]} == set(PROJECTION_TYPES)


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
