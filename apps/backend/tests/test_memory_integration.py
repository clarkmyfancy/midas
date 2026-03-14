from fastapi.testclient import TestClient

from app.main import app
from midas.core.memory import create_clarification_task_for_user


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
    assert "data: - You describe pushing through strain instead of naming it directly." in body

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

    threads_response = client.get(
        "/v1/chat/threads",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert threads_response.status_code == 200
    threads = threads_response.json()["threads"]
    assert len(threads) == 1
    assert threads[0]["title"]
    assert threads[0]["message_count"] == 2

    thread_detail_response = client.get(
        f"/v1/chat/threads/{threads[0]['id']}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert thread_detail_response.status_code == 200
    assert [message["role"] for message in thread_detail_response.json()["messages"]] == [
        "user",
        "assistant",
    ]


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


def test_clarification_resolution_round_trip(monkeypatch) -> None:
    monkeypatch.setattr("app.main.reproject_entry_artifacts", lambda entry, jobs: None)
    monkeypatch.setattr(
        "app.main.run_reflection_workflow",
        lambda payload: type(
            "Response",
            (),
            {"findings": ["Corrected reply after alias resolution."], "summary": "Corrected reply after alias resolution."},
        )(),
    )
    access_token = register_user("clarification-integration@example.com")

    with client.stream(
        "POST",
        "/v1/reflections",
        json={"journal_entry": "Josh joined me after the presentation.", "goals": [], "thread_id": "clarification-thread"},
        headers={"Authorization": f"Bearer {access_token}"},
    ) as create_response:
        assert create_response.status_code == 200
        _ = "".join(create_response.iter_text())

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

    threads_response = client.get(
        "/v1/chat/threads",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert threads_response.status_code == 200
    thread_id = threads_response.json()["threads"][0]["id"]
    thread_detail_response = client.get(
        f"/v1/chat/threads/{thread_id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert thread_detail_response.status_code == 200
    assert thread_detail_response.json()["messages"][-1]["content"] == "- Corrected reply after alias resolution."


def test_clarification_resolution_queues_retry_when_refresh_fails(monkeypatch) -> None:
    def fail_reproject(entry, jobs) -> None:
        raise RuntimeError("Neo4j unavailable")

    monkeypatch.setattr("app.main.reproject_entry_artifacts", fail_reproject)
    access_token = register_user("clarification-retry@example.com")

    with client.stream(
        "POST",
        "/v1/reflections",
        json={"journal_entry": "Tofian was there after the launch.", "goals": [], "thread_id": "clarification-retry"},
        headers={"Authorization": f"Bearer {access_token}"},
    ) as create_response:
        assert create_response.status_code == 200
        _ = "".join(create_response.iter_text())

    run_response = client.post(
        "/v1/projection-jobs/run?limit=10",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert run_response.status_code == 200

    entries_response = client.get(
        "/v1/journal-entries",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert entries_response.status_code == 200
    entry = entries_response.json()["entries"][0]
    entry_id = entry["id"]
    task = create_clarification_task_for_user(
        user_id=entry["user_id"],
        source_record_id=entry_id,
        entity_type="person",
        raw_name="tofian",
        candidate_canonical_name="torian",
        prompt="Does 'tofian' refer to 'Torian' in this entry, or should it stay separate?",
        options=["confirm_merge", "keep_separate", "dismiss"],
        confidence=0.83,
        evidence="'tofian' looks similar to existing person 'torian' and needs confirmation.",
    )

    resolve_response = client.post(
        f"/v1/clarifications/{task.id}/resolve",
        json={"resolution": "confirm_merge"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resolve_response.status_code == 200
    assert resolve_response.json()["status"] == "resolved"
    assert resolve_response.json()["refresh_status"] == "queued"
    assert "queued" in resolve_response.json()["refresh_message"].lower()

    jobs_response = client.get(
        f"/v1/journal-entries/{entry_id}/projection-jobs",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert jobs_response.status_code == 200
    assert {job["status"] for job in jobs_response.json()["projection_jobs"]} == {"pending"}
    assert all(job["last_error"] and "queued after failure" in job["last_error"] for job in jobs_response.json()["projection_jobs"])


def test_clarification_resolution_reprojects_all_entries_with_same_raw_alias(monkeypatch) -> None:
    reprojected_entry_ids: list[str] = []

    def record_reproject(entry, jobs) -> None:
        reprojected_entry_ids.append(entry.id)

    monkeypatch.setattr("app.main.reproject_entry_artifacts", record_reproject)
    access_token = register_user("clarification-sweep@example.com")

    first_response = client.post(
        "/v1/journal-entries",
        json={"journal_entry": "tofian and I talked after lunch", "goals": []},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert first_response.status_code == 200
    first_entry = first_response.json()["entry"]

    second_response = client.post(
        "/v1/journal-entries",
        json={"journal_entry": "I ran into tofian again before heading home", "goals": []},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert second_response.status_code == 200
    second_entry = second_response.json()["entry"]

    third_response = client.post(
        "/v1/journal-entries",
        json={"journal_entry": "torian joined the planning session", "goals": []},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert third_response.status_code == 200
    third_entry = third_response.json()["entry"]

    task = create_clarification_task_for_user(
        user_id=first_entry["user_id"],
        source_record_id=first_entry["id"],
        entity_type="person",
        raw_name="tofian",
        candidate_canonical_name="torian",
        prompt="Does 'tofian' refer to 'Torian' in this entry, or should it stay separate?",
        options=["confirm_merge", "keep_separate", "dismiss"],
        confidence=0.83,
        evidence="'tofian' looks similar to existing person 'torian' and needs confirmation.",
    )

    resolve_response = client.post(
        f"/v1/clarifications/{task.id}/resolve",
        json={"resolution": "confirm_merge"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resolve_response.status_code == 200
    assert resolve_response.json()["refresh_status"] == "refreshed"
    assert set(reprojected_entry_ids) == {first_entry["id"], second_entry["id"]}
    assert third_entry["id"] not in reprojected_entry_ids
