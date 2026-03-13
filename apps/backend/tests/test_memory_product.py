from datetime import datetime

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def register_user(email: str) -> str:
    response = client.post(
        "/v1/auth/register",
        json={"email": email, "password": "supersecret"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_journal_entry_list_is_sorted_newest_first() -> None:
    access_token = register_user("product@example.com")

    first = client.post(
        "/v1/journal-entries",
        json={"journal_entry": "Older entry", "goals": []},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    second = client.post(
        "/v1/journal-entries",
        json={"journal_entry": "Newer entry", "goals": []},
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert first.status_code == 200
    assert second.status_code == 200

    response = client.get(
        "/v1/journal-entries",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    entries = response.json()["entries"]
    assert [entry["journal_entry"] for entry in entries] == ["Newer entry", "Older entry"]
    parsed_times = [datetime.fromisoformat(entry["created_at"]) for entry in entries]
    assert parsed_times[0] >= parsed_times[1]


def test_ingest_response_exposes_processing_state_immediately() -> None:
    access_token = register_user("product-state@example.com")

    response = client.post(
        "/v1/journal-entries",
        json={"journal_entry": "Processing state check", "goals": []},
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["projection_jobs"]
    assert all(job["status"] == "pending" for job in payload["projection_jobs"])
    assert all(job["source_record_id"] == payload["entry"]["id"] for job in payload["projection_jobs"])


def test_debug_payload_exposes_memory_settings() -> None:
    access_token = register_user("debug-settings@example.com")

    create_response = client.post(
        "/v1/journal-entries",
        json={"journal_entry": "Debug payload settings check", "goals": []},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert create_response.status_code == 200
    entry_id = create_response.json()["entry"]["id"]

    debug_response = client.get(
        f"/v1/journal-entries/{entry_id}/debug",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert debug_response.status_code == 200
    assert "settings" in debug_response.json()
    assert debug_response.json()["settings"]["auto_project_enabled"] in {True, False}


def test_clarification_task_contains_user_facing_prompt(monkeypatch) -> None:
    monkeypatch.setenv("MIDAS_AUTO_PROJECT", "0")
    access_token = register_user("clarification-product@example.com")

    create_response = client.post(
        "/v1/journal-entries",
        json={"journal_entry": "Josh and I debriefed after the standup.", "goals": []},
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
    task = clarifications_response.json()["tasks"][0]
    assert "Does 'Josh' refer to" in task["prompt"]
    assert task["options"] == ["confirm_merge", "keep_separate", "dismiss"]
