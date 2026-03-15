from fastapi.testclient import TestClient

from app.main import app
from midas.core.memory import create_clarification_task_for_user
from midas.core.projections import build_weaviate_projection_payload, extract_graph


client = TestClient(app)


class FakeWeaviateProjector:
    objects: dict[str, dict] = {}

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = base_url or "http://127.0.0.1:8080"

    def project(self, job, entry) -> None:
        content, _embedding_text, properties = build_weaviate_projection_payload(job, entry)
        self.objects[job.id] = {
            "class": "MemoryArtifact",
            "id": job.id,
            "properties": {
                **properties,
                "content": content,
            },
        }

    def fetch_object(self, object_id: str):
        return self.objects.get(object_id)

    def delete_objects(self, object_ids: list[str]):
        deleted: list[str] = []
        for object_id in object_ids:
            if object_id in self.objects:
                deleted.append(object_id)
                self.objects.pop(object_id, None)
        from midas.core.projections import WeaviateCleanupResult

        return WeaviateCleanupResult(deleted_object_ids=deleted)

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

    def delete_observation(self, source_record_id: str, user_id: str):
        from midas.core.projections import GraphCleanupResult

        observation = self.observations.pop((user_id, source_record_id), None)
        if observation is None:
            return GraphCleanupResult(
                deleted_observation_ids=[],
                deleted_relationships=0,
                deleted_entities=0,
            )
        observation_node = observation.get("observation")
        observation_id = str(observation_node.get("id")) if observation_node else ""
        return GraphCleanupResult(
            deleted_observation_ids=[observation_id] if observation_id else [],
            deleted_relationships=len(observation.get("relationships", [])),
            deleted_entities=max(len(observation.get("nodes", [])) - 1, 0),
        )

    def browser_url(self) -> str:
        return f"{self.base_url}/browser/"


class TrackingGraphProjector:
    observations: dict[tuple[str, str], dict] = {}

    def __init__(self, base_url: str | None = None, username: str | None = None, password: str | None = None) -> None:
        self.base_url = base_url or "http://127.0.0.1:7474"

    def project(self, job, entry) -> None:
        extraction = extract_graph(entry)
        entity_nodes = [
            {
                "id": f"{job.id}:{entity.canonical_name}",
                "labels": ["Entity", entity.entity_type.title()],
                "properties": {
                    "canonical_name": entity.canonical_name,
                    "display_name": entity.name,
                    "entity_type": entity.entity_type,
                },
            }
            for entity in extraction.entities
        ]
        self.observations[(entry.user_id, entry.id)] = {
            "observation": {
                "id": job.id,
                "labels": ["Observation"],
                "properties": {
                    "source_record_id": entry.id,
                    "summary": extraction.summary,
                },
            },
            "nodes": [
                {
                    "id": job.id,
                    "labels": ["Observation"],
                    "properties": {"source_record_id": entry.id},
                },
                *entity_nodes,
            ],
            "relationships": [],
        }

    def fetch_observation(self, source_record_id: str, user_id: str):
        return self.observations.get(
            (user_id, source_record_id),
            {"observation": None, "nodes": [], "relationships": []},
        )

    def delete_observation(self, source_record_id: str, user_id: str):
        from midas.core.projections import GraphCleanupResult

        observation = self.observations.pop((user_id, source_record_id), None)
        if observation is None:
            return GraphCleanupResult(
                deleted_observation_ids=[],
                deleted_relationships=0,
                deleted_entities=0,
            )
        observation_node = observation.get("observation")
        observation_id = str(observation_node.get("id")) if observation_node else ""
        return GraphCleanupResult(
            deleted_observation_ids=[observation_id] if observation_id else [],
            deleted_relationships=0,
            deleted_entities=max(len(observation.get("nodes", [])) - 1, 0),
        )

    def browser_url(self) -> str:
        return f"{self.base_url}/browser/"


class InsightGraphProjector:
    observations: dict[tuple[str, str], dict] = {}

    def __init__(self, base_url: str | None = None, username: str | None = None, password: str | None = None) -> None:
        self.base_url = base_url or "http://127.0.0.1:7474"

    def project(self, job, entry) -> None:
        extraction = extract_graph(entry)
        node_id_by_canonical_name = {"observation": job.id}
        nodes = [
            {
                "id": job.id,
                "labels": ["Observation"],
                "properties": {"source_record_id": entry.id, "summary": extraction.summary},
            }
        ]
        for entity in extraction.entities:
            node_id = f"{job.id}:{entity.canonical_name}"
            node_id_by_canonical_name[entity.canonical_name] = node_id
            nodes.append(
                {
                    "id": node_id,
                    "labels": ["Entity", entity.entity_type.title()],
                    "properties": {
                        "canonical_name": entity.canonical_name,
                        "display_name": entity.name,
                        "entity_type": entity.entity_type,
                    },
                }
            )

        relationships = [
            {
                "id": f"observed-{job.id}:{entity.canonical_name}",
                "type": "OBSERVED",
                "startNode": job.id,
                "endNode": node_id_by_canonical_name[entity.canonical_name],
                "properties": {
                    "source_record_id": entry.id,
                    "confidence": entity.confidence,
                    "confidence_bucket": "high" if entity.confidence >= 0.85 else "medium",
                    "extraction_source": "system",
                },
            }
            for entity in extraction.entities
        ]
        for index, relationship in enumerate(extraction.relationships):
            source_id = node_id_by_canonical_name.get(relationship.source_canonical_name)
            target_id = node_id_by_canonical_name.get(relationship.target_canonical_name)
            if not source_id or not target_id:
                continue
            relationships.append(
                {
                    "id": f"rel-{job.id}-{index}",
                    "type": relationship.relationship_type.upper(),
                    "startNode": source_id,
                    "endNode": target_id,
                    "properties": {
                        "confidence": relationship.confidence,
                        "confidence_bucket": "high" if relationship.confidence >= 0.85 else ("medium" if relationship.confidence >= 0.65 else "low"),
                        "extraction_source": relationship.extraction_source,
                        "evidence": relationship.evidence,
                    },
                }
            )

        self.observations[(entry.user_id, entry.id)] = {
            "observation": nodes[0],
            "nodes": nodes,
            "relationships": relationships,
        }

    def fetch_observation(self, source_record_id: str, user_id: str):
        return self.observations.get(
            (user_id, source_record_id),
            {"observation": None, "nodes": [], "relationships": []},
        )

    def delete_observation(self, source_record_id: str, user_id: str):
        from midas.core.projections import GraphCleanupResult

        observation = self.observations.pop((user_id, source_record_id), None)
        if observation is None:
            return GraphCleanupResult(
                deleted_observation_ids=[],
                deleted_relationships=0,
                deleted_entities=0,
            )
        observation_node = observation.get("observation")
        observation_id = str(observation_node.get("id")) if observation_node else ""
        return GraphCleanupResult(
            deleted_observation_ids=[observation_id] if observation_id else [],
            deleted_relationships=len(observation.get("relationships", [])),
            deleted_entities=max(len(observation.get("nodes", [])) - 1, 0),
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
    monkeypatch.setenv("MIDAS_AUTO_PROJECT", "0")

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
    monkeypatch.setenv("MIDAS_AUTO_PROJECT", "0")

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


def test_auto_projection_processes_jobs_during_ingest(monkeypatch) -> None:
    FakeWeaviateProjector.objects = {}
    FakeGraphProjector.observations = {}
    monkeypatch.setattr("midas.core.projections.WeaviateProjector", FakeWeaviateProjector)
    monkeypatch.setattr("midas.core.projections.GraphProjector", FakeGraphProjector)
    monkeypatch.setattr("app.main.WeaviateProjector", FakeWeaviateProjector)
    monkeypatch.setattr("app.main.GraphProjector", FakeGraphProjector)
    monkeypatch.setenv("MIDAS_AUTO_PROJECT", "1")

    access_token = register_user("auto-project@example.com")
    response = client.post(
        "/v1/journal-entries",
        json={"journal_entry": "I felt fried after the meeting and skipped my run.", "goals": ["Exercise"]},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200
    entry_id = response.json()["entry"]["id"]

    jobs_response = client.get(
        f"/v1/journal-entries/{entry_id}/projection-jobs",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert jobs_response.status_code == 200
    assert {job["status"] for job in jobs_response.json()["projection_jobs"]} == {"completed"}

    debug_response = client.get(
        f"/v1/journal-entries/{entry_id}/debug",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert debug_response.status_code == 200
    assert debug_response.json()["settings"]["auto_project_enabled"] is True


def test_delete_entry_cascades_into_derived_stores(monkeypatch) -> None:
    FakeWeaviateProjector.objects = {}
    FakeGraphProjector.observations = {}
    monkeypatch.setattr("midas.core.projections.WeaviateProjector", FakeWeaviateProjector)
    monkeypatch.setattr("midas.core.projections.GraphProjector", FakeGraphProjector)
    monkeypatch.setattr("app.main.WeaviateProjector", FakeWeaviateProjector)
    monkeypatch.setattr("app.main.GraphProjector", FakeGraphProjector)
    monkeypatch.setenv("MIDAS_AUTO_PROJECT", "0")

    access_token = register_user("delete-cascade@example.com")
    entry_id = create_entry(access_token, "I was up late finishing a deck and felt ashamed about skipping the gym.")

    run_response = client.post(
        "/v1/projection-jobs/run?limit=10",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert run_response.status_code == 200

    delete_response = client.delete(
        f"/v1/journal-entries/{entry_id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert delete_response.status_code == 200
    payload = delete_response.json()
    assert payload["entry_id"] == entry_id
    assert {item["store"] for item in payload["cleanup"]} == {"weaviate", "neo4j"}
    assert FakeGraphProjector.observations == {}
    assert not any(
        object_payload["properties"]["source_record_id"] == entry_id
        for object_payload in FakeWeaviateProjector.objects.values()
    )


def test_review_endpoint_assembles_hybrid_memory_payload(monkeypatch) -> None:
    FakeWeaviateProjector.objects = {}
    FakeGraphProjector.observations = {}
    monkeypatch.setattr("midas.core.projections.WeaviateProjector", FakeWeaviateProjector)
    monkeypatch.setattr("midas.core.projections.GraphProjector", FakeGraphProjector)
    monkeypatch.setattr("app.main.WeaviateProjector", FakeWeaviateProjector)
    monkeypatch.setattr("app.main.GraphProjector", FakeGraphProjector)
    monkeypatch.setattr("midas.core.review.WeaviateProjector", FakeWeaviateProjector)
    monkeypatch.setattr("midas.core.review.GraphProjector", FakeGraphProjector)
    monkeypatch.setenv("MIDAS_AUTO_PROJECT", "0")

    access_token = register_user("review@example.com")
    me_response = client.get(
        "/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me_response.status_code == 200
    user_id = me_response.json()["id"]
    entry_id = create_entry(access_token, "I felt wrecked after work and skipped my run.")

    run_response = client.post(
        "/v1/projection-jobs/run?limit=10",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert run_response.status_code == 200

    create_clarification_task_for_user(
        user_id=user_id,
        source_record_id=entry_id,
        entity_type="person",
        raw_name="Josh",
        candidate_canonical_name="joshua",
        prompt="Does 'Josh' refer to 'Joshua' in this entry, or should it stay separate?",
        options=["confirm_merge", "keep_separate", "dismiss"],
        confidence=0.63,
        evidence="Alias normalization inferred a merge.",
    )

    review_response = client.get(
        "/v1/review",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert review_response.status_code == 200
    payload = review_response.json()
    assert payload["summary"]
    assert payload["entries"]
    assert payload["memory_highlights"]
    assert len(payload["memory_highlights"]) == 1
    assert payload["memory_highlights"][0]["raw"]["properties"]["content_kind"] == "semantic_summary"
    assert payload["graph"]["nodes"]
    assert payload["clarifications"]


def test_review_endpoint_filters_low_confidence_graph_edges(monkeypatch) -> None:
    class ReviewFilterGraphProjector(FakeGraphProjector):
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
                        "id": f"entity-a-{entry.id}",
                        "labels": ["Entity", "Person"],
                        "properties": {"canonical_name": "self", "display_name": "Self"},
                    },
                    {
                        "id": f"entity-b-{entry.id}",
                        "labels": ["Entity", "Mood"],
                        "properties": {"canonical_name": "anxious", "display_name": "anxious"},
                    },
                    {
                        "id": f"entity-c-{entry.id}",
                        "labels": ["Entity", "Project"],
                        "properties": {"canonical_name": "midas", "display_name": "Midas"},
                    },
                ],
                "relationships": [
                    {
                        "id": f"rel-observed-{entry.id}",
                        "type": "OBSERVED",
                        "startNode": job.id,
                        "endNode": f"entity-a-{entry.id}",
                        "properties": {"source_record_id": entry.id, "confidence": 0.9},
                    },
                    {
                        "id": f"rel-high-{entry.id}",
                        "type": "EXPERIENCED",
                        "startNode": f"entity-a-{entry.id}",
                        "endNode": f"entity-b-{entry.id}",
                        "properties": {"confidence": 0.9, "confidence_bucket": "high", "extraction_source": "model"},
                    },
                    {
                        "id": f"rel-low-{entry.id}",
                        "type": "WORKED_ON",
                        "startNode": f"entity-a-{entry.id}",
                        "endNode": f"entity-c-{entry.id}",
                        "properties": {"confidence": 0.4, "confidence_bucket": "low", "extraction_source": "heuristic"},
                    },
                ],
            }

    FakeWeaviateProjector.objects = {}
    ReviewFilterGraphProjector.observations = {}
    monkeypatch.setattr("midas.core.projections.WeaviateProjector", FakeWeaviateProjector)
    monkeypatch.setattr("midas.core.projections.GraphProjector", ReviewFilterGraphProjector)
    monkeypatch.setattr("app.main.WeaviateProjector", FakeWeaviateProjector)
    monkeypatch.setattr("app.main.GraphProjector", ReviewFilterGraphProjector)
    monkeypatch.setattr("midas.core.review.WeaviateProjector", FakeWeaviateProjector)
    monkeypatch.setattr("midas.core.review.GraphProjector", ReviewFilterGraphProjector)
    monkeypatch.setenv("MIDAS_AUTO_PROJECT", "0")

    access_token = register_user("review-filter@example.com")
    create_entry(access_token, "I felt anxious working on Midas.")

    run_response = client.post(
        "/v1/projection-jobs/run?limit=10",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert run_response.status_code == 200

    filtered_response = client.get(
        "/v1/review?confidence_threshold=0.65",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert filtered_response.status_code == 200
    filtered_relationships = [
        relationship
        for relationship in filtered_response.json()["graph"]["relationships"]
        if relationship["type"] != "OBSERVED"
    ]
    assert [relationship["type"] for relationship in filtered_relationships] == ["EXPERIENCED"]

    unfiltered_response = client.get(
        "/v1/review?confidence_threshold=0.0",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert unfiltered_response.status_code == 200
    unfiltered_relationships = [
        relationship
        for relationship in unfiltered_response.json()["graph"]["relationships"]
        if relationship["type"] != "OBSERVED"
    ]
    assert {relationship["type"] for relationship in unfiltered_relationships} == {"EXPERIENCED", "WORKED_ON"}


def test_insights_endpoint_returns_longitudinal_synthesis(monkeypatch) -> None:
    FakeWeaviateProjector.objects = {}
    InsightGraphProjector.observations = {}
    monkeypatch.setattr("midas.core.projections.WeaviateProjector", FakeWeaviateProjector)
    monkeypatch.setattr("midas.core.projections.GraphProjector", InsightGraphProjector)
    monkeypatch.setattr("app.main.WeaviateProjector", FakeWeaviateProjector)
    monkeypatch.setattr("app.main.GraphProjector", InsightGraphProjector)
    monkeypatch.setattr("midas.core.review.WeaviateProjector", FakeWeaviateProjector)
    monkeypatch.setattr("midas.core.review.GraphProjector", InsightGraphProjector)
    monkeypatch.setattr("midas.core.insights.WeaviateProjector", FakeWeaviateProjector)
    monkeypatch.setattr("midas.core.insights.GraphProjector", InsightGraphProjector)
    monkeypatch.setenv("MIDAS_AUTO_PROJECT", "0")

    access_token = register_user("insights@example.com")
    create_entry(access_token, "I felt anxious about the launch after coffee and a high sugar day.")
    create_entry(access_token, "I spent time with Torian, and the launch was blocked by poor sleep.")

    run_response = client.post(
        "/v1/projection-jobs/run?limit=20",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert run_response.status_code == 200

    insights_response = client.get(
        "/v1/insights?window_days=30&confidence_threshold=0.65",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert insights_response.status_code == 200
    payload = insights_response.json()
    assert payload["summary"]
    assert payload["sections"]
    section_titles = {section["title"] for section in payload["sections"]}
    assert "Patterns" in section_titles
    assert "Tensions" in section_titles
    card_titles = {
        card["title"]
        for section in payload["sections"]
        for card in section["cards"]
    }
    assert "Attention orbit" in card_titles
    assert "Intake signal" in card_titles


def test_resolving_clarification_reprojects_weaviate_and_graph_artifacts(monkeypatch) -> None:
    FakeWeaviateProjector.objects = {}
    TrackingGraphProjector.observations = {}
    monkeypatch.setattr("midas.core.projections.WeaviateProjector", FakeWeaviateProjector)
    monkeypatch.setattr("midas.core.projections.GraphProjector", TrackingGraphProjector)
    monkeypatch.setattr("app.main.WeaviateProjector", FakeWeaviateProjector)
    monkeypatch.setattr("app.main.GraphProjector", TrackingGraphProjector)
    monkeypatch.setenv("MIDAS_AUTO_PROJECT", "0")

    access_token = register_user("clarification-reproject@example.com")
    me_response = client.get(
        "/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me_response.status_code == 200
    user_id = me_response.json()["id"]
    entry_id = create_entry(access_token, "Josh joined me after the presentation.")

    run_response = client.post(
        "/v1/projection-jobs/run?limit=10",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert run_response.status_code == 200

    jobs_response = client.get(
        f"/v1/journal-entries/{entry_id}/projection-jobs",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert jobs_response.status_code == 200
    semantic_job_id = next(
        job["id"]
        for job in jobs_response.json()["projection_jobs"]
        if job["projection_type"] == "weaviate_semantic_summary"
    )

    assert "josh" in FakeWeaviateProjector.objects[semantic_job_id]["properties"]["canonical_entities"]
    assert "joshua" not in FakeWeaviateProjector.objects[semantic_job_id]["properties"]["canonical_entities"]
    initial_graph_entities = {
        node["properties"].get("canonical_name")
        for node in TrackingGraphProjector.observations[(user_id, entry_id)]["nodes"]
        if "canonical_name" in node.get("properties", {})
    }
    assert "josh" in initial_graph_entities
    assert "joshua" not in initial_graph_entities

    task = create_clarification_task_for_user(
        user_id=user_id,
        source_record_id=entry_id,
        entity_type="person",
        raw_name="Josh",
        candidate_canonical_name="joshua",
        prompt="Does 'Josh' refer to 'Joshua' in this entry, or should it stay separate?",
        options=["confirm_merge", "keep_separate", "dismiss"],
        confidence=0.83,
        evidence="'Josh' looks similar to existing person 'Joshua' and needs confirmation.",
    )

    resolve_response = client.post(
        f"/v1/clarifications/{task.id}/resolve",
        json={"resolution": "confirm_merge"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert resolve_response.status_code == 200

    assert "joshua" in FakeWeaviateProjector.objects[semantic_job_id]["properties"]["canonical_entities"]
    updated_graph_entities = {
        node["properties"].get("canonical_name")
        for node in TrackingGraphProjector.observations[(user_id, entry_id)]["nodes"]
        if "canonical_name" in node.get("properties", {})
    }
    assert "joshua" in updated_graph_entities
