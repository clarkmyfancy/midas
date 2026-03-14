from __future__ import annotations

import hashlib
import json
import os
import re
from base64 import b64encode
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from pydantic import BaseModel, Field

from midas.core.memory import (
    create_clarification_task_for_user,
    get_alias_resolution_for_user,
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
    "health_state": "HealthState",
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
    entity_type: str = Field(
        ...,
        description="One of person, place, context, mood, project, habit, goal, substance, health_state.",
    )
    name: str = Field(..., min_length=1)
    canonical_name: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0, le=1)
    evidence: str = Field(..., min_length=1)
    aliases: list[str] = Field(default_factory=list)
    needs_clarification: bool = False
    resolution_notes: str | None = None
    candidate_canonical_name: str | None = None


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


@dataclass(frozen=True)
class WeaviateCleanupResult:
    deleted_object_ids: list[str]


@dataclass(frozen=True)
class GraphCleanupResult:
    deleted_observation_ids: list[str]
    deleted_relationships: int
    deleted_entities: int


def normalize_name(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    return normalized or "unknown"


def sanitize_relationship_type(value: str) -> str:
    lowered = normalize_name(value)
    return lowered if lowered in ALLOWED_RELATIONSHIPS else "about"


PERSON_ALIAS_MAP = {
    "josh": "joshua",
    "joshua": "joshua",
    "matt": "matthew",
    "matthew": "matthew",
    "mike": "michael",
    "michael": "michael",
    "alex": "alexander",
    "alexander": "alexander",
    "sam": "samuel",
    "samuel": "samuel",
    "ben": "benjamin",
    "benjamin": "benjamin",
    "abby": "abigail",
    "abigail": "abigail",
}
PERSON_STOPWORDS = {"After", "Before", "When", "While", "Because", "Later", "Then", "Today", "Yesterday"}
KINSHIP_TITLES = {
    "brother",
    "sister",
    "girlfriend",
    "boyfriend",
    "partner",
    "wife",
    "husband",
    "mom",
    "mother",
    "dad",
    "father",
    "friend",
    "manager",
    "boss",
    "coworker",
    "coworkers",
    "therapist",
}
PLACE_PATTERNS = {
    "home": "home",
    "work": "work",
    "office": "office",
    "park": "park",
    "gym": "gym",
    "kitchen": "kitchen",
    "bedroom": "bedroom",
    "bed": "bed",
    "water cooler": "water cooler",
}
CONTEXT_PATTERNS = {
    "meeting": "meeting",
    "meetings": "meeting",
    "1:1": "one_on_one",
    "standup": "standup",
    "commute": "commute",
    "call": "call",
    "deadline": "deadline",
    "argument": "argument",
    "interview": "interview",
    "presentation": "presentation",
}
PROJECT_PATTERNS = {
    "deck": "deck",
    "presentation": "presentation",
    "launch": "launch",
    "roadmap": "roadmap",
    "proposal": "proposal",
    "sprint": "sprint",
    "project": "project",
}
HABIT_PATTERNS = {
    "workout": "workout",
    "gym": "workout",
    "run": "running",
    "walk": "walking",
    "journal": "journaling",
    "meditate": "meditation",
    "sleep": "sleep",
    "stretch": "stretching",
}
MOOD_PATTERNS = {
    "ashamed": "ashamed",
    "anxious": "anxious",
    "tired": "tired",
    "scattered": "scattered",
    "irritable": "irritable",
    "guilty": "guilty",
    "overwhelmed": "overwhelmed",
    "wired": "wired",
    "drained": "drained",
    "resentful": "resentful",
}
SUBSTANCE_PATTERNS = {
    "weed": "weed",
    "alcohol": "alcohol",
    "medication": "medication",
    "caffeine": "caffeine",
    "coffee": "coffee",
    "nicotine": "nicotine",
}
HEALTH_PATTERNS = {
    "poor sleep": "poor_sleep",
    "slept badly": "poor_sleep",
    "slept poorly": "poor_sleep",
    "low hrv": "low_hrv",
    "exhausted": "exhaustion",
    "burned out": "burnout",
    "low energy": "low_energy",
}
NEGATIVE_HABIT_TERMS = ("skipped", "missed", "avoided", "blew off", "didn't")


def display_name_from_canonical(value: str) -> str:
    return value.replace("_", " ").strip() or value


def canonicalize_entity(
    user_id: str,
    entity_type: str,
    raw_name: str,
) -> tuple[str, list[str], bool, str | None, str | None]:
    cleaned = re.sub(r"\s+", " ", raw_name.strip())
    lowered = cleaned.lower()
    resolution = get_alias_resolution_for_user(
        user_id=user_id,
        entity_type=entity_type,
        raw_name=cleaned,
    )
    if resolution is not None:
        return (
            normalize_name(resolution.resolved_canonical_name),
            [cleaned],
            False,
            f"Applied user clarification '{resolution.resolution}' for '{cleaned}'.",
            None,
        )
    if entity_type == "person":
        tokens = [token for token in re.split(r"[\s\-]+", lowered) if token]
        if tokens:
            canonical_first = PERSON_ALIAS_MAP.get(tokens[0], tokens[0])
            needs_clarification = canonical_first != tokens[0] and len(tokens) == 1
            if needs_clarification:
                return (
                    normalize_name(cleaned),
                    [cleaned],
                    True,
                    f"'{cleaned}' might refer to '{canonical_first}'. Waiting for user confirmation.",
                    normalize_name(" ".join([canonical_first, *tokens[1:]])),
                )
            return normalize_name(" ".join([canonical_first, *tokens[1:]])), [cleaned], False, None, None
    return normalize_name(cleaned), [cleaned], False, None, None


def name_similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, normalize_name(left), normalize_name(right)).ratio()


def is_potential_person_match(left: str, right: str) -> bool:
    left_normalized = normalize_name(left)
    right_normalized = normalize_name(right)
    if not left_normalized or not right_normalized or left_normalized == right_normalized:
        return False
    if left_normalized[0] != right_normalized[0]:
        return False
    if abs(len(left_normalized) - len(right_normalized)) > 2:
        return False
    return name_similarity(left_normalized, right_normalized) >= 0.78


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [part.strip() for part in parts if part.strip()]


def extract_phrase(pattern: str, text: str) -> list[str]:
    matches = re.findall(pattern, text, flags=re.IGNORECASE)
    results: list[str] = []
    for match in matches:
        value = match if isinstance(match, str) else " ".join(match)
        normalized = re.sub(r"\s+", " ", value.strip(" .,!?:;"))
        if normalized:
            results.append(normalized)
    return results


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

    def delete_objects(self, object_ids: list[str]) -> WeaviateCleanupResult:
        deleted_object_ids: list[str] = []
        for object_id in object_ids:
            try:
                call_json_api("DELETE", f"{self.base_url}/v1/objects/{object_id}")
            except RuntimeError as exc:
                if "404" in str(exc):
                    continue
                raise
            deleted_object_ids.append(object_id)
        return WeaviateCleanupResult(deleted_object_ids=deleted_object_ids)

    def object_url(self, object_id: str) -> str:
        return f"{self.base_url}/v1/objects/{object_id}"


def heuristic_extract_graph(entry: JournalEntryRecord) -> GraphExtraction:
    text = entry.journal_entry
    lowered = text.lower()
    entity_index: dict[tuple[str, str], ExtractedEntity] = {}
    relationships: dict[tuple[str, str, str], ExtractedRelationship] = {}

    def add_entity(
        entity_type: str,
        name: str,
        confidence: float,
        evidence: str,
        *,
        needs_clarification: bool = False,
        resolution_notes: str | None = None,
    ) -> ExtractedEntity:
        (
            canonical_name,
            aliases,
            canonical_needs_clarification,
            canonical_note,
            candidate_canonical_name,
        ) = canonicalize_entity(
            entry.user_id,
            entity_type,
            name,
        )
        key = (entity_type, canonical_name)
        current = entity_index.get(key)
        resolved_note = resolution_notes or canonical_note
        resolved_clarification = needs_clarification or canonical_needs_clarification
        display_name = name.strip() or display_name_from_canonical(canonical_name)
        if current is None:
            current = ExtractedEntity(
                entity_type=entity_type,
                name=display_name,
                canonical_name=canonical_name,
                confidence=confidence,
                evidence=evidence,
                aliases=aliases,
                needs_clarification=resolved_clarification,
                resolution_notes=resolved_note,
                candidate_canonical_name=candidate_canonical_name,
            )
        else:
            current = ExtractedEntity(
                entity_type=current.entity_type,
                name=current.name if len(current.name) >= len(display_name) else display_name,
                canonical_name=current.canonical_name,
                confidence=max(current.confidence, confidence),
                evidence=current.evidence if len(current.evidence) >= len(evidence) else evidence,
                aliases=sorted({*current.aliases, *aliases}),
                needs_clarification=current.needs_clarification or resolved_clarification,
                resolution_notes=current.resolution_notes or resolved_note,
                candidate_canonical_name=current.candidate_canonical_name or candidate_canonical_name,
            )
        entity_index[key] = current
        return current

    def add_relationship(
        source_entity: ExtractedEntity,
        target_entity: ExtractedEntity,
        relationship_type: str,
        confidence: float,
        evidence: str,
    ) -> None:
        if source_entity.canonical_name == target_entity.canonical_name:
            return
        relationship_key = (
            source_entity.canonical_name,
            target_entity.canonical_name,
            sanitize_relationship_type(relationship_type),
        )
        current = relationships.get(relationship_key)
        if current is None or confidence > current.confidence:
            relationships[relationship_key] = ExtractedRelationship(
                source_canonical_name=source_entity.canonical_name,
                target_canonical_name=target_entity.canonical_name,
                relationship_type=relationship_key[2],
                confidence=confidence,
                evidence=evidence,
            )

    for token, label in MOOD_PATTERNS.items():
        if token in lowered:
            add_entity("mood", label, 0.72, f"Mentioned mood pattern '{token}'.")
    for token, label in PLACE_PATTERNS.items():
        if token in lowered:
            add_entity("place", label, 0.7, f"Mentioned place pattern '{token}'.")
    for token, label in CONTEXT_PATTERNS.items():
        if token in lowered:
            add_entity("context", label, 0.69, f"Mentioned context pattern '{token}'.")
    for token, label in PROJECT_PATTERNS.items():
        if token in lowered:
            add_entity("project", label, 0.66, f"Mentioned project pattern '{token}'.")
    for token, label in HABIT_PATTERNS.items():
        if token in lowered:
            add_entity("habit", label, 0.67, f"Mentioned habit pattern '{token}'.")
    for token, label in SUBSTANCE_PATTERNS.items():
        if token in lowered:
            add_entity("substance", label, 0.75, f"Mentioned substance pattern '{token}'.")
    for token, label in HEALTH_PATTERNS.items():
        if token in lowered:
            add_entity("health_state", label, 0.78, f"Mentioned health pattern '{token}'.")

    if entry.sleep_hours is not None:
        if entry.sleep_hours < 6:
            add_entity("health_state", "poor_sleep", 0.93, "Derived from sleep_hours below 6.")
        elif entry.sleep_hours >= 7.5:
            add_entity("health_state", "strong_sleep", 0.9, "Derived from sleep_hours at or above 7.5.")
    if entry.hrv_ms is not None:
        if entry.hrv_ms < 35:
            add_entity("health_state", "low_hrv", 0.92, "Derived from hrv_ms below 35.")
        elif entry.hrv_ms >= 55:
            add_entity("health_state", "high_hrv", 0.88, "Derived from hrv_ms at or above 55.")
    if entry.steps is not None and entry.steps < 4000:
        add_entity("habit", "low_movement", 0.83, "Derived from steps below 4000.")

    for goal in entry.goals:
        add_entity("goal", goal, 0.96, "Derived from explicit goals payload.")

    for role in KINSHIP_TITLES:
        if re.search(rf"\b{re.escape(role)}\b", lowered):
            add_entity("person", role, 0.8, f"Mentioned person role '{role}'.")

    for candidate in extract_phrase(r"\b(?:with|to|texted|called|argued with|talked to)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", text):
        add_entity("person", candidate, 0.76, f"Named person mention '{candidate}'.")
    for candidate in re.findall(r"\b[A-Z][a-z]+\b", text):
        if candidate not in {"I", *PERSON_STOPWORDS}:
            add_entity("person", candidate, 0.58, f"Capitalized name candidate '{candidate}'.")

    for candidate in extract_phrase(r"\b(?:at|in|to)\s+the\s+([a-z][a-z\s]{2,30})", lowered):
        if candidate in PLACE_PATTERNS or candidate in CONTEXT_PATTERNS:
            entity_type = "place" if candidate in PLACE_PATTERNS else "context"
            add_entity(entity_type, candidate, 0.64, f"Derived from location phrase '{candidate}'.")

    for candidate in extract_phrase(r"\bworking on\s+([a-z0-9][a-z0-9\s-]{2,40})", lowered):
        add_entity("project", candidate, 0.68, f"Derived from 'working on {candidate}'.")

    sentences = split_sentences(text)
    entities = list(entity_index.values())

    def entity_position(sentence: str, entity: ExtractedEntity) -> int:
        candidates = [entity.name, entity.canonical_name.replace("_", " "), *entity.aliases]
        lowered_sentence = sentence.lower()
        positions = [
            lowered_sentence.find(candidate.lower())
            for candidate in candidates
            if candidate and lowered_sentence.find(candidate.lower()) >= 0
        ]
        return min(positions) if positions else 10**9

    for sentence in sentences:
        sentence_lower = sentence.lower()
        sentence_entities = [
            entity
            for entity in entities
            if any(alias.lower() in sentence_lower for alias in [entity.name, *entity.aliases, entity.canonical_name.replace("_", " ")])
        ]
        sentence_entities.sort(key=lambda entity: entity_position(sentence, entity))
        if len(sentence_entities) < 2:
            continue

        ordered_pairs = list(zip(sentence_entities, sentence_entities[1:]))
        if "after" in sentence_lower:
            for source_entity, target_entity in ordered_pairs:
                add_relationship(source_entity, target_entity, "led_up_to", 0.71, f"Sequential 'after' pattern in '{sentence}'.")
        if "before" in sentence_lower:
            for source_entity, target_entity in ordered_pairs:
                add_relationship(source_entity, target_entity, "precedes", 0.69, f"Sequential 'before' pattern in '{sentence}'.")
        if any(token in sentence_lower for token in ("because", "due to", "from")):
            for source_entity, target_entity in ordered_pairs:
                add_relationship(source_entity, target_entity, "contributed_to", 0.72, f"Causal phrase in '{sentence}'.")
        if "triggered" in sentence_lower:
            for source_entity, target_entity in ordered_pairs:
                add_relationship(source_entity, target_entity, "triggered_by", 0.68, f"Trigger phrase in '{sentence}'.")
        if any(token in sentence_lower for token in ("helped", "supported", "made it easier")):
            for source_entity, target_entity in ordered_pairs:
                add_relationship(source_entity, target_entity, "supported", 0.7, f"Support phrase in '{sentence}'.")

        contexts = [entity for entity in sentence_entities if entity.entity_type in {"context", "project", "place"}]
        impacted = [entity for entity in sentence_entities if entity.entity_type in {"mood", "habit", "health_state"}]
        for source_entity in contexts:
            for target_entity in impacted:
                add_relationship(source_entity, target_entity, "affected", 0.62, f"Shared sentence context in '{sentence}'.")

        substances = [entity for entity in sentence_entities if entity.entity_type == "substance"]
        for source_entity in substances:
            for target_entity in impacted:
                add_relationship(source_entity, target_entity, "affected", 0.66, f"Substance linked to state in '{sentence}'.")

        goals = [entity for entity in sentence_entities if entity.entity_type == "goal"]
        habits = [entity for entity in sentence_entities if entity.entity_type == "habit"]
        if any(token in sentence_lower for token in NEGATIVE_HABIT_TERMS + ("ashamed", "guilty")):
            for habit in habits:
                for goal in goals:
                    add_relationship(habit, goal, "conflicts_with", 0.74, f"Negative habit signal conflicts with goal in '{sentence}'.")

        people = [entity for entity in sentence_entities if entity.entity_type == "person"]
        moods = [entity for entity in sentence_entities if entity.entity_type == "mood"]
        for person in people:
            for mood in moods:
                add_relationship(person, mood, "affected", 0.63, f"Person-state connection in '{sentence}'.")

    goal_entities = [entity for entity in entities if entity.entity_type == "goal"]
    health_entities = [entity for entity in entities if entity.entity_type == "health_state"]
    habit_entities = [entity for entity in entities if entity.entity_type == "habit"]
    if goal_entities and health_entities:
        for health_entity in health_entities:
            for goal_entity in goal_entities:
                add_relationship(health_entity, goal_entity, "affected", 0.58, "Biometric context linked to active goal.")
    if health_entities and habit_entities:
        for health_entity in health_entities:
            for habit_entity in habit_entities:
                add_relationship(health_entity, habit_entity, "affected", 0.61, "Health state linked to behavior in the same entry.")

    entities = list(entity_index.values())
    relationships_list = list(relationships.values())
    if not relationships_list and entities:
        anchor = sorted(
            entities,
            key=lambda entity: (entity.entity_type != "goal", -entity.confidence),
        )[0]
        relationships_list.append(
            ExtractedRelationship(
                source_canonical_name="observation",
                target_canonical_name=anchor.canonical_name,
                relationship_type="about",
                confidence=0.6,
                evidence="Fallback observation link.",
            )
        )

    prominent_entities = sorted(
        entities,
        key=lambda entity: (entity.entity_type != "goal", -entity.confidence, entity.name),
    )[:4]
    if prominent_entities:
        summary = "Key factors: " + ", ".join(
            f"{entity.entity_type.replace('_', ' ')}={display_name_from_canonical(entity.canonical_name)}"
            for entity in prominent_entities
        )
    else:
        summary = build_episode_summary(entry)
    return GraphExtraction(summary=summary, entities=entities, relationships=relationships_list)


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
                "Extract a compact but personally useful knowledge graph from this journal entry.",
                "Use only entity types: person, place, context, mood, project, habit, goal, substance, health_state.",
                "Use only relationship types: affected, supported, conflicts_with, led_up_to, triggered_by, precedes, causes, recurs, about, contributed_to, experienced.",
                "Canonicalize aliases when they likely refer to the same thing, for example Josh and Joshua.",
                "If an alias merge is plausible but uncertain, set needs_clarification=true and explain why in resolution_notes.",
                "When uncertain, keep the raw person name as the entity itself and put the suggested merge target in candidate_canonical_name.",
                "Return concise evidence grounded in the journal text or biometric payload. Do not invent entities.",
                f"Journal entry: {entry.journal_entry}",
                f"Goals: {', '.join(entry.goals) if entry.goals else 'None provided'}",
                f"Sleep hours: {entry.sleep_hours if entry.sleep_hours is not None else 'unknown'}",
                f"HRV ms: {entry.hrv_ms if entry.hrv_ms is not None else 'unknown'}",
                f"Steps: {entry.steps if entry.steps is not None else 'unknown'}",
            ]
        )
        return llm.invoke(prompt)

    def list_entities(self, user_id: str, entity_type: str) -> list[dict[str, Any]]:
        try:
            result = self._query(
                """
                MATCH (e:Entity {user_id: $user_id, entity_type: $entity_type})
                RETURN e.canonical_name AS canonical_name,
                       e.display_name AS display_name,
                       coalesce(e.aliases, []) AS aliases,
                       coalesce(e.max_confidence, 0.0) AS max_confidence,
                       coalesce(e.observation_count, 0) AS observation_count
                ORDER BY observation_count DESC, max_confidence DESC
                LIMIT 200
                """,
                {"user_id": user_id, "entity_type": entity_type},
            )
        except RuntimeError:
            return []
        rows = result.get("results", [{}])[0].get("data", [])
        return [dict(zip(("canonical_name", "display_name", "aliases", "max_confidence", "observation_count"), row.get("row", []), strict=False)) for row in rows]

    def _prepare_entity_for_storage(
        self,
        entry: JournalEntryRecord,
        entity: ExtractedEntity,
        existing_people: list[dict[str, Any]],
    ) -> ExtractedEntity:
        aliases = sorted({alias.strip() for alias in [entity.name, *entity.aliases] if alias.strip()})
        raw_canonical_name = normalize_name(entity.name)
        candidate_canonical_name = (
            normalize_name(entity.candidate_canonical_name)
            if entity.candidate_canonical_name
            else None
        )

        if entity.needs_clarification:
            if candidate_canonical_name is None and entity.canonical_name != raw_canonical_name:
                candidate_canonical_name = normalize_name(entity.canonical_name)
            return ExtractedEntity(
                entity_type=entity.entity_type,
                name=entity.name,
                canonical_name=raw_canonical_name,
                confidence=min(entity.confidence, 0.72),
                evidence=entity.evidence,
                aliases=aliases,
                needs_clarification=True,
                resolution_notes=entity.resolution_notes,
                candidate_canonical_name=candidate_canonical_name,
            )

        if entity.entity_type != "person":
            return ExtractedEntity(
                entity_type=entity.entity_type,
                name=entity.name,
                canonical_name=normalize_name(entity.canonical_name),
                confidence=entity.confidence,
                evidence=entity.evidence,
                aliases=aliases,
                needs_clarification=False,
                resolution_notes=entity.resolution_notes,
                candidate_canonical_name=None,
            )

        best_match: dict[str, Any] | None = None
        best_score = 0.0
        for candidate in existing_people:
            candidate_canonical = normalize_name(str(candidate.get("canonical_name") or candidate.get("display_name") or ""))
            if not is_potential_person_match(raw_canonical_name, candidate_canonical):
                continue
            score = name_similarity(raw_canonical_name, candidate_canonical)
            if score > best_score:
                best_match = candidate
                best_score = score

        if best_match is None:
            return ExtractedEntity(
                entity_type=entity.entity_type,
                name=entity.name,
                canonical_name=normalize_name(entity.canonical_name),
                confidence=entity.confidence,
                evidence=entity.evidence,
                aliases=aliases,
                needs_clarification=False,
                resolution_notes=entity.resolution_notes,
                candidate_canonical_name=None,
            )

        candidate_canonical_name = normalize_name(
            str(best_match.get("canonical_name") or best_match.get("display_name") or raw_canonical_name)
        )
        return ExtractedEntity(
            entity_type=entity.entity_type,
            name=entity.name,
            canonical_name=raw_canonical_name,
            confidence=min(entity.confidence, round(best_score, 2)),
            evidence=entity.evidence,
            aliases=aliases,
            needs_clarification=True,
            resolution_notes=(
                f"'{entity.name}' looks similar to existing person "
                f"'{display_name_from_canonical(candidate_canonical_name)}' and needs confirmation."
            ),
            candidate_canonical_name=candidate_canonical_name,
        )

    def prepare_extraction(self, entry: JournalEntryRecord, extraction: GraphExtraction) -> GraphExtraction:
        existing_people = self.list_entities(entry.user_id, "person")
        prepared_entities: list[ExtractedEntity] = []
        canonical_name_map: dict[str, str] = {}
        for entity in extraction.entities:
            prepared = self._prepare_entity_for_storage(entry, entity, existing_people)
            prepared_entities.append(prepared)
            canonical_name_map[entity.canonical_name] = prepared.canonical_name

        prepared_relationships: list[ExtractedRelationship] = []
        for relationship in extraction.relationships:
            prepared_relationships.append(
                ExtractedRelationship(
                    source_canonical_name=canonical_name_map.get(
                        relationship.source_canonical_name,
                        relationship.source_canonical_name,
                    ),
                    target_canonical_name=canonical_name_map.get(
                        relationship.target_canonical_name,
                        relationship.target_canonical_name,
                    ),
                    relationship_type=relationship.relationship_type,
                    confidence=relationship.confidence,
                    evidence=relationship.evidence,
                )
            )
        return GraphExtraction(
            summary=extraction.summary,
            entities=prepared_entities,
            relationships=prepared_relationships,
        )

    def project(self, job: ProjectionJobRecord, entry: JournalEntryRecord) -> None:
        extraction = self.prepare_extraction(entry, self.extract(entry))
        for entity in extraction.entities:
            if not entity.needs_clarification or not entity.aliases:
                continue
            raw_name = entity.name
            candidate_canonical_name = entity.candidate_canonical_name or entity.canonical_name
            candidate_display_name = display_name_from_canonical(candidate_canonical_name).title()
            create_clarification_task_for_user(
                user_id=entry.user_id,
                source_record_id=entry.id,
                entity_type=entity.entity_type,
                raw_name=raw_name,
                candidate_canonical_name=candidate_canonical_name,
                prompt=(
                    f"Does '{raw_name}' refer to '{candidate_display_name}' in this entry, "
                    f"or should it stay separate?"
                ),
                options=["confirm_merge", "keep_separate", "dismiss"],
                confidence=entity.confidence,
                evidence=entity.resolution_notes or entity.evidence,
            )

        self.ensure_schema()
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
                SET e.aliases = CASE
                    WHEN e.aliases IS NULL OR size(e.aliases) = 0 THEN $aliases
                    ELSE reduce(acc = e.aliases, alias IN $aliases |
                        CASE WHEN alias IN acc THEN acc ELSE acc + alias END)
                  END,
                    e.needs_clarification = coalesce(e.needs_clarification, false) OR $needs_clarification,
                    e.resolution_notes = coalesce(e.resolution_notes, $resolution_notes),
                    e.observation_count = coalesce(e.observation_count, 0) + 1,
                    e.last_seen_at = $created_at,
                    e.max_confidence = CASE
                        WHEN e.max_confidence IS NULL OR e.max_confidence < $confidence THEN $confidence
                        ELSE e.max_confidence
                    END
                WITH e
                MATCH (o:Observation {{id: $observation_id}})
                MERGE (o)-[r:OBSERVED {{source_record_id: $source_record_id, entity_key: $entity_key}}]->(e)
                SET r.confidence = $confidence,
                    r.evidence = $evidence,
                    r.entity_type = $entity_type
                """,
                {
                    "entity_key": entity_key,
                    "user_id": entry.user_id,
                    "entity_type": entity.entity_type,
                    "canonical_name": entity.canonical_name,
                    "display_name": entity.name,
                    "aliases": entity.aliases,
                    "needs_clarification": entity.needs_clarification,
                    "resolution_notes": entity.resolution_notes,
                    "observation_id": observation_id,
                    "source_record_id": entry.id,
                    "created_at": entry.created_at.isoformat(),
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
                    r.evidence = $evidence,
                    r.provenance = $provenance
                """,
                {
                    "source_key": known_entities[relation.source_canonical_name]["key"],
                    "target_key": known_entities[relation.target_canonical_name]["key"],
                    "source_record_id": entry.id,
                    "observation_id": observation_id,
                    "confidence": relation.confidence,
                    "evidence": relation.evidence,
                    "provenance": f"journal_entry:{entry.id}",
                },
            )

    def delete_observation(self, source_record_id: str, user_id: str) -> GraphCleanupResult:
        result = self._query(
            """
            MATCH (o:Observation {source_record_id: $source_record_id, user_id: $user_id})
            RETURN collect(o.id) AS observation_ids
            """,
            {"source_record_id": source_record_id, "user_id": user_id},
        )
        rows = result.get("results", [{}])[0].get("data", [])
        if not rows:
            return GraphCleanupResult(
                deleted_observation_ids=[],
                deleted_relationships=0,
                deleted_entities=0,
            )
        observation_ids = rows[0].get("row", [[]])[0]
        if not observation_ids:
            return GraphCleanupResult(
                deleted_observation_ids=[],
                deleted_relationships=0,
                deleted_entities=0,
            )

        deleted_relationships_result = self._query(
            """
            MATCH ()-[r]-()
            WHERE r.source_record_id = $source_record_id OR r.observation_id IN $observation_ids
            WITH collect(r) AS relationships
            FOREACH (relationship IN relationships | DELETE relationship)
            RETURN size(relationships) AS deleted_relationships
            """,
            {
                "source_record_id": source_record_id,
                "observation_ids": observation_ids,
            },
        )
        deleted_relationships = 0
        deleted_relationship_rows = deleted_relationships_result.get("results", [{}])[0].get("data", [])
        if deleted_relationship_rows:
            deleted_relationships = int(deleted_relationship_rows[0].get("row", [0])[0])

        self._query(
            """
            MATCH (o:Observation {source_record_id: $source_record_id, user_id: $user_id})
            DETACH DELETE o
            """,
            {"source_record_id": source_record_id, "user_id": user_id},
        )

        deleted_entities_result = self._query(
            """
            MATCH (e:Entity {user_id: $user_id})
            WHERE NOT (e)--()
            WITH collect(e) AS entities
            FOREACH (entity IN entities | DELETE entity)
            RETURN size(entities) AS deleted_entities
            """,
            {"user_id": user_id},
        )
        deleted_entities = 0
        deleted_entity_rows = deleted_entities_result.get("results", [{}])[0].get("data", [])
        if deleted_entity_rows:
            deleted_entities = int(deleted_entity_rows[0].get("row", [0])[0])

        return GraphCleanupResult(
            deleted_observation_ids=[str(item) for item in observation_ids],
            deleted_relationships=deleted_relationships,
            deleted_entities=deleted_entities,
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


def delete_derived_artifacts(
    entry: JournalEntryRecord,
    jobs: list[ProjectionJobRecord],
) -> tuple[WeaviateCleanupResult, GraphCleanupResult]:
    weaviate_job_ids = [job.id for job in jobs if job.projection_type.startswith("weaviate_")]
    weaviate = WeaviateProjector()
    graph = GraphProjector()
    weaviate_result = weaviate.delete_objects(weaviate_job_ids)
    graph_result = graph.delete_observation(entry.id, entry.user_id)
    return weaviate_result, graph_result
