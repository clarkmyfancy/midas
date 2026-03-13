from __future__ import annotations

import hashlib
import json
import os
import re
from base64 import b64encode
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from pydantic import BaseModel, Field

from midas.core.memory import (
    JournalEntryRecord,
    ProjectionJobRecord,
    get_journal_entry_for_user,
    list_pending_projection_jobs,
    mark_projection_job_completed,
    mark_projection_job_failed,
)


VECTOR_CLASS_NAME = "MemoryArtifact"
GRAPH_ENTITY_LABELS = {
    "context": "Context",
    "goal": "Goal",
    "habit": "Habit",
    "mood": "Mood",
    "person": "Person",
    "place": "Place",
    "project": "Project",
    "substance": "Substance",
}
ALLOWED_RELATIONSHIPS = {
    "affected",
    "supported",
    "conflicts_with",
    "led_up_to",
    "triggered_by",
    "precedes",
    "causes",
    "recurs",
    "about",
    "contributed_to",
    "experienced",
}


class ExtractedEntity(BaseModel):
    entity_type: str = Field(..., description="One of person, place, context, mood, project, habit, goal, substance.")
    name: str = Field(..., min_length=1)
    canonical_name: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0, le=1)
    evidence: str = Field(..., min_length=1)


class ExtractedRelationship(BaseModel):
    source_canonical_name: str = Field(..., min_length=1)
    target_canonical_name: str = Field(..., min_length=1)
    relationship_type: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0, le=1)
    evidence: str = Field(..., min_length=1)


class GraphExtraction(BaseModel):
    summary: str
    entities: list[ExtractedEntity]
    relationships: list[ExtractedRelationship]


@dataclass(frozen=True)
class ProjectionRunResult:
    claimed_jobs: int
    completed_jobs: int
    failed_jobs: int
    jobs: list[ProjectionJobRecord]


def normalize_name(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    return normalized or "unknown"


def sanitize_relationship_type(value: str) -> str:
    lowered = normalize_name(value)
    return lowered if lowered in ALLOWED_RELATIONSHIPS else "about"


def deterministic_vector(text: str, *, dimensions: int = 16) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    values: list[float] = []
    for index in range(dimensions):
        chunk = digest[(index * 2) % len(digest) : ((index * 2) % len(digest)) + 2]
        if len(chunk) < 2:
            chunk = (chunk + digest)[:2]
        raw = int.from_bytes(chunk, "big")
        values.append((raw / 65535.0) * 2 - 1)
    return values


def embed_text(text: str) -> list[float]:
    if os.getenv("OPENAI_API_KEY"):
        embedding = OpenAIEmbeddings(model="text-embedding-3-small")
        return embedding.embed_query(text)
    return deterministic_vector(text)


def build_episode_summary(entry: JournalEntryRecord) -> str:
    metrics: list[str] = []
    if entry.steps is not None:
        metrics.append(f"steps {entry.steps}")
    if entry.sleep_hours is not None:
        metrics.append(f"sleep {entry.sleep_hours:.1f}h")
    if entry.hrv_ms is not None:
        metrics.append(f"HRV {entry.hrv_ms:.1f}ms")

    metrics_text = ", ".join(metrics) if metrics else "no biometric context"
    goals_text = ", ".join(entry.goals) if entry.goals else "no explicit goals"
    return (
        f"Episode summary: {entry.journal_entry} Goals: {goals_text}. "
        f"Context: {metrics_text}. Source: {entry.source}."
    )


def call_json_api(
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request_headers = {"Accept": "application/json"}
    if payload is not None:
        request_headers["Content-Type"] = "application/json"
    if headers:
        request_headers.update(headers)

    request = Request(url, data=body, headers=request_headers, method=method)
    try:
        with urlopen(request, timeout=10) as response:
            content = response.read().decode("utf-8")
    except HTTPError as exc:  # pragma: no cover - network path
        detail = exc.read().decode("utf-8")
        raise RuntimeError(f"{method} {url} failed with {exc.code}: {detail}") from exc
    except URLError as exc:  # pragma: no cover - network path
        raise RuntimeError(f"{method} {url} failed: {exc.reason}") from exc

    return json.loads(content) if content else {}


class WeaviateProjector:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or os.getenv("WEAVIATE_URL") or "http://127.0.0.1:8080").rstrip("/")

    def ensure_schema(self) -> None:
        schema = call_json_api("GET", f"{self.base_url}/v1/schema")
        classes = {item.get("class") for item in schema.get("classes", [])}
        if VECTOR_CLASS_NAME in classes:
            return

        call_json_api(
            "POST",
            f"{self.base_url}/v1/schema",
            payload={
                "class": VECTOR_CLASS_NAME,
                "vectorizer": "none",
                "properties": [
                    {"name": "user_id", "dataType": ["text"]},
                    {"name": "source_record_id", "dataType": ["text"]},
                    {"name": "source_record_type", "dataType": ["text"]},
                    {"name": "projection_type", "dataType": ["text"]},
                    {"name": "content", "dataType": ["text"]},
                    {"name": "source", "dataType": ["text"]},
                    {"name": "thread_id", "dataType": ["text"]},
                    {"name": "goals_json", "dataType": ["text"]},
                    {"name": "created_at", "dataType": ["text"]},
                ],
            },
        )

    def project(self, job: ProjectionJobRecord, entry: JournalEntryRecord) -> None:
        self.ensure_schema()
        content = (
            entry.journal_entry
            if job.projection_type == "weaviate_journal_memory"
            else build_episode_summary(entry)
        )
        call_json_api(
            "POST",
            f"{self.base_url}/v1/objects",
            payload={
                "class": VECTOR_CLASS_NAME,
                "id": job.id,
                "properties": {
                    "user_id": entry.user_id,
                    "source_record_id": entry.id,
                    "source_record_type": job.source_record_type,
                    "projection_type": job.projection_type,
                    "content": content,
                    "source": entry.source,
                    "thread_id": entry.thread_id or "",
                    "goals_json": json.dumps(entry.goals),
                    "created_at": entry.created_at.isoformat(),
                },
                "vector": embed_text(content),
            },
        )

    def fetch_object(self, object_id: str) -> dict[str, Any] | None:
        try:
            return call_json_api("GET", f"{self.base_url}/v1/objects/{object_id}")
        except RuntimeError:
            return None

    def object_url(self, object_id: str) -> str:
        return f"{self.base_url}/v1/objects/{object_id}"


def heuristic_extract_graph(entry: JournalEntryRecord) -> GraphExtraction:
    text = entry.journal_entry
    lowered = text.lower()
    entities: list[ExtractedEntity] = []
    relationships: list[ExtractedRelationship] = []

    def add_entity(entity_type: str, name: str, confidence: float, evidence: str) -> None:
        canonical_name = normalize_name(name)
        if any(item.canonical_name == canonical_name for item in entities):
            return
        entities.append(
            ExtractedEntity(
                entity_type=entity_type,
                name=name,
                canonical_name=canonical_name,
                confidence=confidence,
                evidence=evidence,
            )
        )

    mood_keywords = {"ashamed": "ashamed", "anxious": "anxious", "tired": "tired", "scattered": "scattered"}
    place_keywords = {"home": "home", "work": "work", "park": "park"}
    substance_keywords = {"weed": "weed", "alcohol": "alcohol", "medication": "medication"}
    context_keywords = {"meeting": "meeting", "water cooler": "water cooler", "commute": "commute"}

    for token, label in mood_keywords.items():
        if token in lowered:
            add_entity("mood", label, 0.72, f"Mentioned mood keyword '{token}'")
    for token, label in place_keywords.items():
        if token in lowered:
            add_entity("place", label, 0.7, f"Mentioned place keyword '{token}'")
    for token, label in substance_keywords.items():
        if token in lowered:
            add_entity("substance", label, 0.75, f"Mentioned substance keyword '{token}'")
    for token, label in context_keywords.items():
        if token in lowered:
            add_entity("context", label, 0.68, f"Mentioned context keyword '{token}'")

    for goal in entry.goals:
        add_entity("goal", goal, 0.94, "Derived from explicit goals payload")

    capitalized_names = re.findall(r"\b[A-Z][a-z]+\b", entry.journal_entry)
    for name in capitalized_names:
        add_entity("person", name, 0.55, f"Capitalized token '{name}' may refer to a person")

    if entities:
        first_entity = entities[0]
        relationships.append(
            ExtractedRelationship(
                source_canonical_name="observation",
                target_canonical_name=first_entity.canonical_name,
                relationship_type="about",
                confidence=0.6,
                evidence="Fallback observation link",
            )
        )

    summary = build_episode_summary(entry)
    return GraphExtraction(summary=summary, entities=entities, relationships=relationships)


class GraphProjector:
    def __init__(self, base_url: str | None = None, username: str | None = None, password: str | None = None) -> None:
        self.base_url = (base_url or os.getenv("NEO4J_HTTP_URL") or "http://127.0.0.1:7474").rstrip("/")
        self.username = username or os.getenv("NEO4J_USERNAME") or "neo4j"
        self.password = password or os.getenv("NEO4J_PASSWORD") or "midasdevpassword"

    def _headers(self) -> dict[str, str]:
        token = b64encode(f"{self.username}:{self.password}".encode("utf-8")).decode("utf-8")
        return {"Authorization": f"Basic {token}"}

    def _query(self, statement: str, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
        return call_json_api(
            "POST",
            f"{self.base_url}/db/neo4j/tx/commit",
            payload={
                "statements": [
                    {
                        "statement": statement,
                        "parameters": parameters or {},
                        "resultDataContents": ["graph", "row"],
                    }
                ]
            },
            headers=self._headers(),
        )

    def ensure_schema(self) -> None:
        self._query(
            "CREATE CONSTRAINT observation_id IF NOT EXISTS FOR (o:Observation) REQUIRE o.id IS UNIQUE"
        )
        self._query(
            "CREATE CONSTRAINT entity_key IF NOT EXISTS FOR (e:Entity) REQUIRE e.entity_key IS UNIQUE"
        )

    def extract(self, entry: JournalEntryRecord) -> GraphExtraction:
        if not os.getenv("OPENAI_API_KEY"):
            return heuristic_extract_graph(entry)

        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0).with_structured_output(GraphExtraction)
        prompt = "\n".join(
            [
                "Extract a compact knowledge graph from this journal entry.",
                "Use only entity types: person, place, context, mood, project, habit, goal, substance.",
                "Use only relationship types: affected, supported, conflicts_with, led_up_to, triggered_by, precedes, causes, recurs, about, contributed_to, experienced.",
                "Return confidence scores and preserve concise evidence.",
                f"Journal entry: {entry.journal_entry}",
                f"Goals: {', '.join(entry.goals) if entry.goals else 'None provided'}",
            ]
        )
        return llm.invoke(prompt)

    def project(self, job: ProjectionJobRecord, entry: JournalEntryRecord) -> None:
        self.ensure_schema()
        extraction = self.extract(entry)
        observation_id = job.id
        self._query(
            """
            MERGE (o:Observation {id: $observation_id})
            SET o.user_id = $user_id,
                o.source_record_id = $source_record_id,
                o.source_record_type = $source_record_type,
                o.projection_type = $projection_type,
                o.summary = $summary,
                o.journal_entry = $journal_entry,
                o.created_at = $created_at
            """,
            {
                "observation_id": observation_id,
                "user_id": entry.user_id,
                "source_record_id": entry.id,
                "source_record_type": job.source_record_type,
                "projection_type": job.projection_type,
                "summary": extraction.summary,
                "journal_entry": entry.journal_entry,
                "created_at": entry.created_at.isoformat(),
            },
        )

        known_entities = {"observation": {"label": "Observation", "key": observation_id}}
        for entity in extraction.entities:
            label = GRAPH_ENTITY_LABELS.get(entity.entity_type, "Entity")
            entity_key = f"{entry.user_id}:{entity.entity_type}:{entity.canonical_name}"
            known_entities[entity.canonical_name] = {"label": label, "key": entity_key}
            self._query(
                f"""
                MERGE (e:Entity:{label} {{entity_key: $entity_key}})
                SET e.user_id = $user_id,
                    e.entity_type = $entity_type,
                    e.canonical_name = $canonical_name,
                    e.display_name = $display_name
                WITH e
                MATCH (o:Observation {{id: $observation_id}})
                MERGE (o)-[r:OBSERVED {{source_record_id: $source_record_id, entity_key: $entity_key}}]->(e)
                SET r.confidence = $confidence,
                    r.evidence = $evidence
                """,
                {
                    "entity_key": entity_key,
                    "user_id": entry.user_id,
                    "entity_type": entity.entity_type,
                    "canonical_name": entity.canonical_name,
                    "display_name": entity.name,
                    "observation_id": observation_id,
                    "source_record_id": entry.id,
                    "confidence": entity.confidence,
                    "evidence": entity.evidence,
                },
            )

        for relation in extraction.relationships:
            if relation.source_canonical_name not in known_entities:
                continue
            if relation.target_canonical_name not in known_entities:
                continue
            relationship_type = sanitize_relationship_type(relation.relationship_type).upper()
            source_match_field = (
                "id"
                if relation.source_canonical_name == "observation"
                else "entity_key"
            )
            target_match_field = (
                "id"
                if relation.target_canonical_name == "observation"
                else "entity_key"
            )
            self._query(
                f"""
                MATCH (source {{{source_match_field}: $source_key}})
                MATCH (target {{{target_match_field}: $target_key}})
                MERGE (source)-[r:{relationship_type} {{source_record_id: $source_record_id, observation_id: $observation_id}}]->(target)
                SET r.confidence = $confidence,
                    r.evidence = $evidence
                """,
                {
                    "source_key": known_entities[relation.source_canonical_name]["key"],
                    "target_key": known_entities[relation.target_canonical_name]["key"],
                    "source_record_id": entry.id,
                    "observation_id": observation_id,
                    "confidence": relation.confidence,
                    "evidence": relation.evidence,
                },
            )

    def fetch_observation(self, source_record_id: str, user_id: str) -> dict[str, Any]:
        result = self._query(
            """
            MATCH (o:Observation {source_record_id: $source_record_id, user_id: $user_id})
            OPTIONAL MATCH (o)-[r]-(n)
            RETURN o,
                   collect(DISTINCT n) AS nodes,
                   collect(DISTINCT r) AS relationships
            """,
            {"source_record_id": source_record_id, "user_id": user_id},
        )
        results = result.get("results", [])
        if not results:
            return {"observation": None, "nodes": [], "relationships": []}
        data = results[0].get("data", [])
        if not data:
            return {"observation": None, "nodes": [], "relationships": []}
        graph = data[0].get("graph", {})
        nodes = graph.get("nodes", [])
        relationships = graph.get("relationships", [])
        observation = None
        for node in nodes:
            labels = node.get("labels", [])
            if "Observation" in labels:
                observation = node
                break
        return {
            "observation": observation,
            "nodes": nodes,
            "relationships": relationships,
        }

    def browser_url(self) -> str:
        return urljoin(f"{self.base_url}/", "browser/")


def serialize_neo4j_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: serialize_neo4j_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [serialize_neo4j_value(item) for item in value]
    return value


def process_pending_projection_jobs(*, limit: int = 10, user_id: str | None = None) -> ProjectionRunResult:
    jobs = list_pending_projection_jobs(limit=limit, user_id=user_id)
    completed: list[ProjectionJobRecord] = []
    failed: list[ProjectionJobRecord] = []
    weaviate = WeaviateProjector()
    graph = GraphProjector()

    for job in jobs:
        entry = get_journal_entry_for_user(job.user_id, job.source_record_id)
        if entry is None:
            failed.append(mark_projection_job_failed(job.id, "Canonical journal entry not found"))
            continue

        try:
            if job.projection_type.startswith("weaviate_"):
                weaviate.project(job, entry)
            elif job.projection_type == "neo4j_knowledge_graph":
                graph.project(job, entry)
            else:
                raise RuntimeError(f"Unsupported projection type {job.projection_type}")
        except Exception as exc:  # pragma: no cover - exercised through tests with stubs
            failed.append(mark_projection_job_failed(job.id, str(exc)))
        else:
            completed.append(mark_projection_job_completed(job.id))

    return ProjectionRunResult(
        claimed_jobs=len(jobs),
        completed_jobs=len(completed),
        failed_jobs=len(failed),
        jobs=[*completed, *failed],
    )
