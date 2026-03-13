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


def test_journal_entry_ingestion_returns_entry_and_projection_jobs() -> None:
    access_token = register_user("memory@example.com")

    response = client.post(
        "/v1/journal-entries",
        json={
            "journal_entry": "I felt scattered after meetings and skipped my workout.",
            "goals": ["Protect focus", "Exercise"],
            "thread_id": "morning-checkin",
            "steps": 4100,
            "sleep_hours": 5.9,
            "hrv_ms": 34.0,
        },
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["entry"]["journal_entry"].startswith("I felt scattered")
    assert payload["entry"]["thread_id"] == "morning-checkin"
    assert payload["entry"]["source"] == "manual"
    assert len(payload["projection_jobs"]) == 3
    assert {job["status"] for job in payload["projection_jobs"]} == {"pending"}


def test_reflection_endpoint_persists_canonical_journal_entry() -> None:
    access_token = register_user("reflection-memory@example.com")

    with client.stream(
        "POST",
        "/v1/reflections",
        json={
            "journal_entry": "I kept saying I was fine, but my body felt cooked.",
            "goals": ["Protect recovery"],
            "thread_id": "evening-reflection",
        },
        headers={"Authorization": f"Bearer {access_token}"},
    ) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert "data: - Semantic drift:" in body

    list_response = client.get(
        "/v1/journal-entries",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert list_response.status_code == 200
    entries = list_response.json()["entries"]
    assert len(entries) == 1
    assert entries[0]["source"] == "reflection_api"
    assert entries[0]["thread_id"] == "evening-reflection"

    jobs_response = client.get(
        f"/v1/journal-entries/{entries[0]['id']}/projection-jobs",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert jobs_response.status_code == 200
    assert len(jobs_response.json()["projection_jobs"]) == 3


def test_delete_endpoint_removes_canonical_entry() -> None:
    access_token = register_user("delete-integration@example.com")

    create_response = client.post(
        "/v1/journal-entries",
        json={"journal_entry": "Delete integration check", "goals": ["Protect recovery"]},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert create_response.status_code == 200
    entry_id = create_response.json()["entry"]["id"]

    delete_response = client.delete(
        f"/v1/journal-entries/{entry_id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["entry_id"] == entry_id

    get_response = client.get(
        f"/v1/journal-entries/{entry_id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    list_response = client.get(
        "/v1/journal-entries",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert get_response.status_code == 404
    assert list_response.json()["entries"] == []


def test_clarification_resolution_round_trip() -> None:
    access_token = register_user("clarification-integration@example.com")

    create_response = client.post(
        "/v1/journal-entries",
        json={"journal_entry": "Josh joined me after the presentation.", "goals": []},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert create_response.status_code == 200

    run_response = client.post(
        "/v1/projection-jobs/run?limit=10",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert run_response.status_code == 200

    list_response = client.get(
        "/v1/clarifications",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert list_response.status_code == 200
    task = list_response.json()["tasks"][0]

    resolve_response = client.post(
        f"/v1/clarifications/{task['id']}/resolve",
        json={"resolution": "keep_separate"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resolve_response.status_code == 200
    assert resolve_response.json()["status"] == "resolved"
    assert resolve_response.json()["resolution"] == "keep_separate"

    resolved_list_response = client.get(
        "/v1/clarifications?task_status=resolved",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resolved_list_response.status_code == 200
    assert resolved_list_response.json()["tasks"][0]["id"] == task["id"]
