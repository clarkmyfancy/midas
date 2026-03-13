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


def create_entry(access_token: str, text: str) -> str:
    response = client.post(
        "/v1/journal-entries",
        json={"journal_entry": text, "goals": []},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200
    return response.json()["entry"]["id"]


def test_user_cannot_read_another_users_journal_entry_or_jobs() -> None:
    owner_token = register_user("owner@example.com")
    viewer_token = register_user("viewer@example.com")
    entry_id = create_entry(owner_token, "Private journal entry.")

    entry_response = client.get(
        f"/v1/journal-entries/{entry_id}",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    jobs_response = client.get(
        f"/v1/journal-entries/{entry_id}/projection-jobs",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    assert entry_response.status_code == 404
    assert jobs_response.status_code == 404


def test_user_cannot_delete_another_users_journal_entry() -> None:
    owner_token = register_user("delete-owner@example.com")
    viewer_token = register_user("delete-viewer@example.com")
    entry_id = create_entry(owner_token, "Private entry to delete.")

    delete_response = client.delete(
        f"/v1/journal-entries/{entry_id}",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    owner_list_response = client.get(
        "/v1/journal-entries",
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert delete_response.status_code == 404
    assert [entry["id"] for entry in owner_list_response.json()["entries"]] == [entry_id]


def test_user_cannot_view_or_resolve_another_users_clarification_tasks(monkeypatch) -> None:
    monkeypatch.setenv("MIDAS_AUTO_PROJECT", "0")
    owner_token = register_user("clarify-owner@example.com")
    viewer_token = register_user("clarify-viewer@example.com")

    create_response = client.post(
        "/v1/journal-entries",
        json={"journal_entry": "Josh stayed after the meeting.", "goals": []},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert create_response.status_code == 200

    run_response = client.post(
        "/v1/projection-jobs/run?limit=10",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert run_response.status_code == 200

    owner_tasks_response = client.get(
        "/v1/clarifications",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert owner_tasks_response.status_code == 200
    task_id = owner_tasks_response.json()["tasks"][0]["id"]

    viewer_list_response = client.get(
        "/v1/clarifications",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    viewer_resolve_response = client.post(
        f"/v1/clarifications/{task_id}/resolve",
        json={"resolution": "dismiss"},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )

    assert viewer_list_response.status_code == 200
    assert viewer_list_response.json()["tasks"] == []
    assert viewer_resolve_response.status_code == 404


def test_list_endpoint_only_returns_current_users_entries() -> None:
    first_token = register_user("first@example.com")
    second_token = register_user("second@example.com")
    create_entry(first_token, "First user entry.")
    create_entry(second_token, "Second user entry.")

    first_response = client.get(
        "/v1/journal-entries",
        headers={"Authorization": f"Bearer {first_token}"},
    )
    second_response = client.get(
        "/v1/journal-entries",
        headers={"Authorization": f"Bearer {second_token}"},
    )

    assert [entry["journal_entry"] for entry in first_response.json()["entries"]] == [
        "First user entry."
    ]
    assert [entry["journal_entry"] for entry in second_response.json()["entries"]] == [
        "Second user entry."
    ]
