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
