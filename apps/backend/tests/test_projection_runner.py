from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


class FakeWeaviateProjector:
    objects: dict[str, dict] = {}

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = base_url or "http://127.0.0.1:8080"

    def project(self, job, entry) -> None:
        content = (
            entry.journal_entry
            if job.projection_type == "weaviate_journal_memory"
            else f"Episode summary: {entry.journal_entry}"
        )
        self.objects[job.id] = {
            "class": "MemoryArtifact",
            "id": job.id,
            "properties": {
                "content": content,
                "source_record_id": entry.id,
                "projection_type": job.projection_type,
            },
        }

    def fetch_object(self, object_id: str):
        return self.objects.get(object_id)

    def object_url(self, object_id: str) -> str:
        return f"{self.base_url}/v1/objects/{object_id}"


class FakeGraphProjector:
    observations: dict[tuple[str, str], dict] = {}

    def __init__(self, base_url: str | None = None, username: str | None = None, password: str | None = None) -> None:
        self.base_url = base_url or "http://127.0.0.1:7474"

    def project(self, job, entry) -> None:
        self.observations[(entry.user_id, entry.id)] = {
            "observation": {
                "id": job.id,
                "labels": ["Observation"],
                "properties": {
                    "source_record_id": entry.id,
                    "summary": f"Graph summary for {entry.id}",
                },
            },
            "nodes": [
                {
                    "id": job.id,
                    "labels": ["Observation"],
                    "properties": {"source_record_id": entry.id},
                },
                {
                    "id": f"entity-{entry.id}",
                    "labels": ["Entity", "Goal"],
                    "properties": {"canonical_name": "protect_recovery"},
                },
            ],
            "relationships": [
                {
                    "id": f"rel-{entry.id}",
                    "type": "OBSERVED",
                    "startNode": job.id,
                    "endNode": f"entity-{entry.id}",
                    "properties": {"source_record_id": entry.id, "confidence": 0.9},
                }
            ],
        }

    def fetch_observation(self, source_record_id: str, user_id: str):
        return self.observations.get(
            (user_id, source_record_id),
            {"observation": None, "nodes": [], "relationships": []},
        )

    def browser_url(self) -> str:
        return f"{self.base_url}/browser/"


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
        json={"journal_entry": text, "goals": ["Protect recovery"]},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200
    return response.json()["entry"]["id"]


def test_projection_runner_completes_pending_jobs_and_debug_endpoint_exposes_artifacts(monkeypatch) -> None:
    FakeWeaviateProjector.objects = {}
    FakeGraphProjector.observations = {}
    monkeypatch.setattr("midas.core.projections.WeaviateProjector", FakeWeaviateProjector)
    monkeypatch.setattr("midas.core.projections.GraphProjector", FakeGraphProjector)
    monkeypatch.setattr("app.main.WeaviateProjector", FakeWeaviateProjector)
    monkeypatch.setattr("app.main.GraphProjector", FakeGraphProjector)

    access_token = register_user("projector@example.com")
    entry_id = create_entry(access_token, "I felt wrecked after work and skipped my run.")

    run_response = client.post(
        "/v1/projection-jobs/run?limit=10",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert run_response.status_code == 200
    payload = run_response.json()
    assert payload["claimed_jobs"] == 3
    assert payload["completed_jobs"] == 3
    assert payload["failed_jobs"] == 0
    assert {job["status"] for job in payload["jobs"]} == {"completed"}

    debug_response = client.get(
        f"/v1/journal-entries/{entry_id}/debug",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert debug_response.status_code == 200
    debug_payload = debug_response.json()
    assert len(debug_payload["weaviate_artifacts"]) == 2
    assert debug_payload["graph"]["observation"] is not None
    assert debug_payload["graph"]["nodes"]
    assert debug_payload["graph"]["relationships"]
    assert debug_payload["links"]["neo4j_browser"].endswith("/browser/")


def test_projection_runner_only_claims_current_users_jobs(monkeypatch) -> None:
    FakeWeaviateProjector.objects = {}
    FakeGraphProjector.observations = {}
    monkeypatch.setattr("midas.core.projections.WeaviateProjector", FakeWeaviateProjector)
    monkeypatch.setattr("midas.core.projections.GraphProjector", FakeGraphProjector)
    monkeypatch.setattr("app.main.WeaviateProjector", FakeWeaviateProjector)
    monkeypatch.setattr("app.main.GraphProjector", FakeGraphProjector)

    first_token = register_user("first-projector@example.com")
    second_token = register_user("second-projector@example.com")
    create_entry(first_token, "First user pending jobs")
    second_entry_id = create_entry(second_token, "Second user pending jobs")

    first_run_response = client.post(
        "/v1/projection-jobs/run?limit=10",
        headers={"Authorization": f"Bearer {first_token}"},
    )
    assert first_run_response.status_code == 200
    assert first_run_response.json()["claimed_jobs"] == 3

    second_jobs_response = client.get(
        f"/v1/journal-entries/{second_entry_id}/projection-jobs",
        headers={"Authorization": f"Bearer {second_token}"},
    )
    assert second_jobs_response.status_code == 200
    assert {job["status"] for job in second_jobs_response.json()["projection_jobs"]} == {
        "pending"
    }
