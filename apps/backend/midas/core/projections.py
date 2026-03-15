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
    LEGACY_WEAVIATE_RAW_JOURNAL_PROJECTION,
    LEGACY_WEAVIATE_SEMANTIC_SUMMARY_PROJECTION,
    ProjectionJobRecord,
    WEAVIATE_RAW_JOURNAL_PROJECTION,
    WEAVIATE_SEMANTIC_SUMMARY_PROJECTION,
    get_journal_entry_for_user,
    list_pending_projection_jobs,
    mark_projection_job_completed,
    mark_projection_job_failed,
)
from midas.core.runtime import allow_test_external_store_access, is_test_mode


VECTOR_CLASS_NAME = "MemoryArtifact"
GRAPH_ENTITY_LABELS = {
    "context": "Context",
    "goal": "Goal",
    "habit": "Habit",
    "health_state": "HealthState",
    "intake": "Intake",
    "mood": "Mood",
    "organization": "Organization",
    "person": "Person",
    "place": "Place",
    "project": "Project",
}
ALLOWED_ENTITY_TYPES = {
    "context",
    "goal",
    "habit",
    "health_state",
    "intake",
    "mood",
    "organization",
    "person",
    "place",
    "project",
}
ALLOWED_RELATIONSHIPS = {
    "affected",
    "about",
    "blocked_by",
    "causes",
    "conflicts_with",
    "consumed",
    "contributed_to",
    "avoided",
    "experienced",
    "felt_about",
    "followed",
    "interacted_with",
    "led_up_to",
    "precedes",
    "recurs",
    "spent_time_with",
    "supported",
    "triggered_by",
    "used",
    "worked_on",
}


def allows_local_defaults() -> bool:
    environment = os.getenv("MIDAS_ENV") or os.getenv("NODE_ENV") or "development"
    return environment.strip().lower() in {"dev", "development", "local", "test", "testing"}


def resolve_neo4j_password(password: str | None) -> str:
    resolved_password = password or os.getenv("NEO4J_PASSWORD")
    if resolved_password:
        if not allows_local_defaults() and resolved_password == "midasdevpassword":
            raise RuntimeError("NEO4J_PASSWORD must not use the development default outside development and test")
        return resolved_password

    if allows_local_defaults():
        return "midasdevpassword"

    raise RuntimeError("NEO4J_PASSWORD is required outside development and test")
WEAVIATE_PROJECTION_VERSION = "v2"
WEAVIATE_CLASS_PROPERTIES = [
    {"name": "user_id", "dataType": ["text"], "indexFilterable": True, "indexSearchable": False},
    {"name": "source_record_id", "dataType": ["text"], "indexFilterable": True, "indexSearchable": False},
    {"name": "source_record_type", "dataType": ["text"], "indexFilterable": True, "indexSearchable": False},
    {"name": "projection_type", "dataType": ["text"], "indexFilterable": True, "indexSearchable": False},
    {"name": "projection_version", "dataType": ["text"], "indexFilterable": True, "indexSearchable": False},
    {"name": "content_kind", "dataType": ["text"], "indexFilterable": True, "indexSearchable": False},
    {"name": "content", "dataType": ["text"], "indexFilterable": True, "indexSearchable": True, "tokenization": "word"},
    {"name": "normalized_content", "dataType": ["text"], "indexFilterable": False, "indexSearchable": True, "tokenization": "word"},
    {"name": "source", "dataType": ["text"], "indexFilterable": True, "indexSearchable": False},
    {"name": "thread_id", "dataType": ["text"], "indexFilterable": True, "indexSearchable": False},
    {"name": "goals", "dataType": ["text[]"], "indexFilterable": True, "indexSearchable": False},
    {"name": "goals_text", "dataType": ["text"], "indexFilterable": False, "indexSearchable": True, "tokenization": "word"},
    {"name": "intakes", "dataType": ["text[]"], "indexFilterable": True, "indexSearchable": False},
    {"name": "people", "dataType": ["text[]"], "indexFilterable": True, "indexSearchable": False},
    {"name": "organizations", "dataType": ["text[]"], "indexFilterable": True, "indexSearchable": False},
    {"name": "projects", "dataType": ["text[]"], "indexFilterable": True, "indexSearchable": False},
    {"name": "contexts", "dataType": ["text[]"], "indexFilterable": True, "indexSearchable": False},
    {"name": "moods", "dataType": ["text[]"], "indexFilterable": True, "indexSearchable": False},
    {"name": "canonical_entities", "dataType": ["text[]"], "indexFilterable": True, "indexSearchable": False},
    {"name": "created_at", "dataType": ["date"], "indexFilterable": True, "indexRangeFilters": True},
]
COMMON_TYPO_CORRECTIONS = {
    "becasue": "because",
    "communicting": "communicating",
    "definately": "definitely",
    "recieve": "receive",
    "seperate": "separate",
}
PROJECT_STOPWORDS = {
    "app",
    "current",
    "it",
    "local",
    "now",
    "one",
    "project",
    "recent",
    "setup",
    "that",
    "thing",
    "this",
    "today",
}
PEOPLE_STOPWORDS = {
    "and",
    "hang",
    "it",
    "one",
    "that",
    "the",
    "this",
    "with",
}
NEGATIVE_COLLABORATION_TERMS = ("tough", "conflict", "blamed", "insulted", "throats", "issues", "argued")
POSITIVE_COLLABORATION_TERMS = ("fun", "laughing", "great", "pumped", "working", "good")
INTERACTION_TERMS = (
    "talked with",
    "talking with",
    "working with",
    "met with",
    "hang with",
    "argued with",
    "texted",
    "called",
    "debriefed with",
    "laughing with",
)
SPENT_TIME_TERMS = (
    "hang with",
    "hung with",
    "spent time with",
    "grabbed dinner with",
    "went out with",
    "kicked it with",
)
WORK_ACTIVITY_TERMS = (
    "working on",
    "worked on",
    "building",
    "built",
    "developing",
    "implemented",
    "implementing",
    "set up",
    "setup",
    "shipping",
    "launched",
    "coding",
)
EMOTION_TARGET_TERMS = (
    "about",
    "around",
    "regarding",
    "toward",
    "towards",
)
BLOCKED_BY_TERMS = (
    "blocked by",
    "stuck because of",
    "held up by",
    "slowed by",
    "derailed by",
    "couldn't because of",
)
PERSON_ACTION_TERMS = (
    "said",
    "stayed",
    "joined",
    "helped",
    "blamed",
    "asked",
    "debriefed",
    "told",
    "met",
    "texted",
    "called",
    "emailed",
    "mentioned",
)
INTAKE_CONSUMPTION_TERMS = (
    "drank",
    "drink",
    "drinking",
    "ate",
    "eating",
    "consumed",
    "had",
    "after",
)
INTAKE_USE_TERMS = (
    "used",
    "using",
    "smoked",
    "smoking",
    "vaped",
    "vaping",
    "took",
    "taking",
)
INTAKE_AVOIDANCE_TERMS = (
    "avoided",
    "avoid",
    "skipped",
    "skip",
    "stayed sober",
    "staying sober",
    "didn't drink",
    "didnt drink",
    "did not drink",
    "without",
    "cut out",
)


class ExtractedEntity(BaseModel):
    entity_type: str = Field(
        ...,
        description="One of person, organization, place, context, mood, project, habit, goal, intake, health_state.",
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
    extraction_source: str = Field(default="model", min_length=1)


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
class WeaviateLocalCleanupResult:
    deleted_class: bool


@dataclass(frozen=True)
class GraphCleanupResult:
    deleted_observation_ids: list[str]
    deleted_relationships: int
    deleted_entities: int


@dataclass(frozen=True)
class GraphUserCleanupResult:
    deleted_observations: int
    deleted_entities: int
    deleted_relationships: int


@dataclass(frozen=True)
class GraphLocalCleanupResult:
    deleted_observations: int
    deleted_entities: int
    deleted_relationships: int


def normalize_name(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    return normalized or "unknown"


def sanitize_relationship_type(value: str) -> str:
    lowered = normalize_name(value)
    return lowered if lowered in ALLOWED_RELATIONSHIPS else "about"


def sanitize_entity_type(value: str) -> str | None:
    lowered = normalize_name(value)
    if lowered in {"company", "org", "organisation"}:
        return "organization"
    if lowered in {"substance", "consumable"}:
        return "intake"
    return lowered if lowered in ALLOWED_ENTITY_TYPES else None


def confidence_bucket_for_confidence(confidence: float) -> str:
    if confidence >= 0.85:
        return "high"
    if confidence >= 0.65:
        return "medium"
    return "low"


def sanitize_extraction_source(value: str | None) -> str:
    normalized = normalize_name(value or "")
    if normalized in {"heuristic", "model", "normalized", "system"}:
        return normalized
    return "model"


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
CURRENT_USER_CANONICAL_NAME = "self"
CURRENT_USER_REFERENCES = {
    "i",
    "me",
    "my",
    "mine",
    "myself",
    "self",
}
PERSON_PLACEHOLDER_REFERENCES = {
    "unknown",
    "unnamed",
    "author",
    "user",
    "journal author",
}
PERSON_STOPWORDS = {"After", "Before", "When", "While", "Because", "Later", "Then", "Today", "Yesterday", "Sometimes"}
SUMMARY_NOISE_TOKENS = {"sometimes", "something", "someone", "everything", "nothing"}
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
    "excited": "excited",
    "great": "great",
    "pumped": "pumped",
    "tired": "tired",
    "scattered": "scattered",
    "irritable": "irritable",
    "guilty": "guilty",
    "overwhelmed": "overwhelmed",
    "wired": "wired",
    "drained": "drained",
    "resentful": "resentful",
}
INTAKE_PATTERNS = {
    "weed": "weed",
    "alcohol": "alcohol",
    "medication": "medication",
    "caffeine": "caffeine",
    "coffee": "coffee",
    "nicotine": "nicotine",
    "high sugar": "high_sugar",
    "sugar": "sugar",
    "edible": "edible",
    "edibles": "edibles",
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


def is_current_user_reference(value: str) -> bool:
    return normalize_name(value) in CURRENT_USER_REFERENCES


def is_placeholder_person_reference(value: str) -> bool:
    return normalize_name(value) in {normalize_name(item) for item in PERSON_PLACEHOLDER_REFERENCES}


def canonicalize_entity(
    user_id: str,
    entity_type: str,
    raw_name: str,
) -> tuple[str, list[str], bool, str | None, str | None]:
    cleaned = re.sub(r"\s+", " ", raw_name.strip())
    lowered = cleaned.lower()
    if entity_type == "person" and is_current_user_reference(cleaned):
        return CURRENT_USER_CANONICAL_NAME, [cleaned], False, None, None
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


def extract_case_sensitive_phrase(pattern: str, text: str) -> list[str]:
    matches = re.findall(pattern, text)
    results: list[str] = []
    for match in matches:
        value = match if isinstance(match, str) else " ".join(match)
        normalized = re.sub(r"\s+", " ", value.strip(" .,!?:;"))
        if normalized:
            results.append(normalized)
    return results


def is_valid_person_candidate(value: str) -> bool:
    normalized = normalize_name(value)
    if not normalized or normalized == CURRENT_USER_CANONICAL_NAME:
        return False
    tokens = [token for token in normalized.split("_") if token]
    if not tokens:
        return False
    if any(token in PEOPLE_STOPWORDS or token in SUMMARY_NOISE_TOKENS for token in tokens):
        return False
    if any(token in PROJECT_STOPWORDS for token in tokens):
        return False
    return True


def is_valid_project_candidate(value: str) -> bool:
    normalized = normalize_name(value)
    if not normalized:
        return False
    tokens = [token for token in normalized.split("_") if token]
    if not tokens:
        return False
    if any(token in PROJECT_STOPWORDS or token in SUMMARY_NOISE_TOKENS for token in tokens):
        return False
    if len(tokens) > 3:
        return False
    return True


def is_valid_organization_candidate(value: str) -> bool:
    normalized = normalize_name(value)
    if not normalized:
        return False
    tokens = [token for token in normalized.split("_") if token]
    if not tokens:
        return False
    if any(token in PROJECT_STOPWORDS or token in SUMMARY_NOISE_TOKENS for token in tokens):
        return False
    if len(tokens) > 5:
        return False
    return True


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


def normalize_free_text(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text.strip())
    for typo, correction in COMMON_TYPO_CORRECTIONS.items():
        normalized = re.sub(rf"\b{re.escape(typo)}\b", correction, normalized, flags=re.IGNORECASE)
    return normalized


def format_display_list(values: list[str]) -> str:
    unique_values = [value for value in dict.fromkeys(value.strip() for value in values if value.strip())]
    if not unique_values:
        return ""
    if len(unique_values) == 1:
        return unique_values[0]
    if len(unique_values) == 2:
        return f"{unique_values[0]} and {unique_values[1]}"
    return ", ".join(unique_values[:-1]) + f", and {unique_values[-1]}"


def entity_display_names(
    extraction: GraphExtraction,
    entity_type: str,
    *,
    include_self: bool = True,
    allow_generic: bool = True,
) -> list[str]:
    names: list[str] = []
    for entity in extraction.entities:
        if entity.entity_type != entity_type:
            continue
        if entity.entity_type == "person" and (entity.canonical_name == CURRENT_USER_CANONICAL_NAME or is_current_user_reference(entity.name)):
            if not include_self:
                continue
        display_name = normalize_free_text(entity.name if entity.name.strip() else display_name_from_canonical(entity.canonical_name))
        normalized_display_name = normalize_name(display_name)
        if any(token in SUMMARY_NOISE_TOKENS for token in normalized_display_name.split("_")):
            continue
        if not allow_generic and normalized_display_name in {"project", "work", "home"}:
            continue
        if entity_type == "person" and not is_valid_person_candidate(display_name):
            continue
        if entity_type == "project" and not is_valid_project_candidate(display_name):
            continue
        if entity_type == "organization" and not is_valid_organization_candidate(display_name):
            continue
        if entity_type == "person":
            display_name = display_name.title()
        else:
            display_name = display_name.replace("_", " ")
        names.append(display_name)
    return list(dict.fromkeys(names))


def canonical_entity_names(extraction: GraphExtraction) -> list[str]:
    return list(
        dict.fromkeys(
            entity.canonical_name
            for entity in extraction.entities
            if entity.canonical_name
            and entity.canonical_name not in {"observation", CURRENT_USER_CANONICAL_NAME, "project", "work", "home"}
            and not any(token in SUMMARY_NOISE_TOKENS for token in normalize_name(entity.canonical_name).split("_"))
            and (
                entity.entity_type not in {"person", "project"}
                or (
                    is_valid_person_candidate(entity.canonical_name)
                    if entity.entity_type == "person"
                    else is_valid_project_candidate(entity.canonical_name)
                )
            )
            and (
                entity.entity_type != "organization"
                or is_valid_organization_candidate(entity.canonical_name)
            )
        )
    )


def prune_people_against_projects(people: list[str], projects: list[str]) -> list[str]:
    project_names = {normalize_name(project) for project in projects}
    return [
        person
        for person in people
        if normalize_name(person) not in project_names
    ]


def build_semantic_memory_summary(entry: JournalEntryRecord, extraction: GraphExtraction) -> str:
    lowered_entry = entry.journal_entry.lower()
    projects = entity_display_names(extraction, "project", allow_generic=False)
    organizations = entity_display_names(extraction, "organization", allow_generic=False)
    people = prune_people_against_projects(
        entity_display_names(extraction, "person", include_self=False, allow_generic=False),
        [*projects, *organizations],
    )
    contexts = [
        *entity_display_names(extraction, "context", allow_generic=False),
        *entity_display_names(extraction, "place", allow_generic=False),
    ]
    moods = entity_display_names(extraction, "mood")
    habits = entity_display_names(extraction, "habit")
    health_states = entity_display_names(extraction, "health_state")
    intakes = entity_display_names(extraction, "intake")
    goals = [normalize_free_text(goal) for goal in entry.goals]

    segments: list[str] = []
    has_negative_collaboration = any(term in lowered_entry for term in NEGATIVE_COLLABORATION_TERMS)
    has_positive_collaboration = any(term in lowered_entry for term in POSITIVE_COLLABORATION_TERMS)

    if projects and people:
        project_text = format_display_list(projects)
        people_text = format_display_list(people)
        if has_negative_collaboration and has_positive_collaboration:
            segments.append(
                f"Mixed collaboration with {people_text} on {project_text}, including both positive moments and conflict."
            )
        elif has_negative_collaboration:
            segments.append(
                f"Strained collaboration with {people_text} on {project_text}."
            )
        else:
            segments.append(
                f"Work on {project_text} involving {people_text}."
            )
    elif projects:
        segments.append(f"Work centered on {format_display_list(projects)}.")
    elif organizations:
        segments.append(f"Organization context: {format_display_list(organizations)}.")
    elif people:
        if has_negative_collaboration:
            segments.append(f"Tense interaction involving {format_display_list(people)}.")
        else:
            segments.append(f"Interaction involving {format_display_list(people)}.")
    elif contexts:
        segments.append(f"Context centered on {format_display_list(contexts)}.")

    if moods or health_states:
        state_values = moods + health_states
        segments.append(f"State signal: {format_display_list(state_values)}.")
    if intakes:
        segments.append(f"Intake signal: {format_display_list(intakes)}.")
    if habits and goals:
        segments.append(
            f"Behavioral thread: {format_display_list(habits)} in relation to goals {format_display_list(goals)}."
        )
    elif habits:
        segments.append(f"Behavioral thread: {format_display_list(habits)}.")
    elif goals:
        segments.append(f"Active goals: {format_display_list(goals)}.")
    if contexts and not projects:
        segments.append(f"Relevant context: {format_display_list(contexts)}.")
    if organizations and not projects:
        segments.append(f"Relevant organization: {format_display_list(organizations)}.")

    if not segments:
        compressed = normalize_free_text(entry.journal_entry)
        trimmed = " ".join(compressed.split()[:20]).rstrip(".,;:!?")
        segments.append(f"Journal note about {trimmed}.")
    return " ".join(segment.strip() for segment in segments if segment.strip())


def build_weaviate_projection_payload(
    job: ProjectionJobRecord,
    entry: JournalEntryRecord,
    extraction: GraphExtraction | None = None,
) -> tuple[str, str, dict[str, Any]]:
    extraction = normalize_extraction(entry, extraction or extract_graph(entry))
    normalized_content = normalize_free_text(entry.journal_entry)
    goals = [normalize_free_text(goal) for goal in entry.goals]
    projects = entity_display_names(extraction, "project", allow_generic=False)
    organizations = entity_display_names(extraction, "organization", allow_generic=False)
    intakes = entity_display_names(extraction, "intake", allow_generic=False)
    people = prune_people_against_projects(
        entity_display_names(extraction, "person", include_self=False, allow_generic=False),
        [*projects, *organizations],
    )
    metadata = {
        "user_id": entry.user_id,
        "source_record_id": entry.id,
        "source_record_type": job.source_record_type,
        "projection_type": job.projection_type,
        "projection_version": WEAVIATE_PROJECTION_VERSION,
        "source": entry.source,
        "thread_id": entry.thread_id or "",
        "goals": goals,
        "goals_text": ", ".join(goals),
        "intakes": intakes,
        "people": people,
        "organizations": organizations,
        "projects": projects,
        "contexts": [
            *entity_display_names(extraction, "context", allow_generic=False),
            *entity_display_names(extraction, "place", allow_generic=False),
        ],
        "moods": [*entity_display_names(extraction, "mood"), *entity_display_names(extraction, "health_state")],
        "canonical_entities": canonical_entity_names(extraction),
        "created_at": entry.created_at.isoformat(),
    }

    if job.projection_type in {
        WEAVIATE_RAW_JOURNAL_PROJECTION,
        LEGACY_WEAVIATE_RAW_JOURNAL_PROJECTION,
    }:
        content = entry.journal_entry
        metadata["content_kind"] = "raw_journal_entry"
        metadata["normalized_content"] = normalized_content
        embedding_text = "\n".join(
            filter(
                None,
                [
                    normalized_content,
                    metadata["goals_text"],
                    ", ".join(metadata["intakes"]),
                    ", ".join(metadata["people"]),
                    ", ".join(metadata["organizations"]),
                    ", ".join(metadata["projects"]),
                    ", ".join(metadata["contexts"]),
                    ", ".join(metadata["moods"]),
                ],
            )
        )
        return content, embedding_text, metadata

    content = build_semantic_memory_summary(entry, extraction)
    metadata["content_kind"] = "semantic_summary"
    metadata["normalized_content"] = content
    embedding_text = "\n".join(
        filter(
            None,
            [
                content,
                normalized_content,
                metadata["goals_text"],
                ", ".join(metadata["intakes"]),
                ", ".join(metadata["organizations"]),
                ", ".join(metadata["canonical_entities"]),
            ],
        )
    )
    return content, embedding_text, metadata


def call_json_api(
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    if is_test_mode() and not allow_test_external_store_access():
        raise RuntimeError(
            "External Weaviate and Neo4j access is disabled during tests. "
            "Patch the projectors or set MIDAS_ALLOW_TEST_EXTERNAL_STORES=1 explicitly."
        )

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


def weaviate_request_headers(api_key: str | None = None) -> dict[str, str]:
    resolved_api_key = (api_key or os.getenv("WEAVIATE_API_KEY") or "").strip()
    if not resolved_api_key:
        return {}
    return {"Authorization": f"Bearer {resolved_api_key}"}


class WeaviateProjector:
    def __init__(self, base_url: str | None = None, api_key: str | None = None) -> None:
        self.base_url = (base_url or os.getenv("WEAVIATE_URL") or "http://127.0.0.1:8080").rstrip("/")
        self.api_key = api_key

    def _headers(self) -> dict[str, str]:
        return weaviate_request_headers(self.api_key)

    def ensure_schema(self) -> None:
        schema = call_json_api("GET", f"{self.base_url}/v1/schema", headers=self._headers())
        classes_by_name = {
            str(item.get("class")): item for item in schema.get("classes", []) if item.get("class")
        }
        current_class = classes_by_name.get(VECTOR_CLASS_NAME)
        if current_class is None:
            call_json_api(
                "POST",
                f"{self.base_url}/v1/schema",
                payload={
                    "class": VECTOR_CLASS_NAME,
                    "vectorizer": "none",
                    "properties": WEAVIATE_CLASS_PROPERTIES,
                },
                headers=self._headers(),
            )
            return

        existing_property_names = {
            str(property_item.get("name"))
            for property_item in current_class.get("properties", [])
            if property_item.get("name")
        }
        for property_definition in WEAVIATE_CLASS_PROPERTIES:
            if property_definition["name"] in existing_property_names:
                continue
            call_json_api(
                "POST",
                f"{self.base_url}/v1/schema/{VECTOR_CLASS_NAME}/properties",
                payload=property_definition,
                headers=self._headers(),
            )

    def project(self, job: ProjectionJobRecord, entry: JournalEntryRecord) -> None:
        self.ensure_schema()
        content, embedding_text, properties = build_weaviate_projection_payload(job, entry)
        call_json_api(
            "POST",
            f"{self.base_url}/v1/objects",
            payload={
                "class": VECTOR_CLASS_NAME,
                "id": job.id,
                "properties": {
                    **properties,
                    "content": content,
                },
                "vector": embed_text(embedding_text),
            },
            headers=self._headers(),
        )

    def fetch_object(self, object_id: str) -> dict[str, Any] | None:
        try:
            return call_json_api("GET", f"{self.base_url}/v1/objects/{object_id}", headers=self._headers())
        except RuntimeError:
            return None

    def delete_objects(self, object_ids: list[str]) -> WeaviateCleanupResult:
        deleted_object_ids: list[str] = []
        for object_id in object_ids:
            try:
                call_json_api("DELETE", f"{self.base_url}/v1/objects/{object_id}", headers=self._headers())
            except RuntimeError as exc:
                if "404" in str(exc):
                    continue
                raise
            deleted_object_ids.append(object_id)
        return WeaviateCleanupResult(deleted_object_ids=deleted_object_ids)

    def delete_local_data(self) -> WeaviateLocalCleanupResult:
        schema = call_json_api("GET", f"{self.base_url}/v1/schema", headers=self._headers())
        classes = {item.get("class") for item in schema.get("classes", [])}
        if VECTOR_CLASS_NAME not in classes:
            return WeaviateLocalCleanupResult(deleted_class=False)
        call_json_api("DELETE", f"{self.base_url}/v1/schema/{VECTOR_CLASS_NAME}", headers=self._headers())
        return WeaviateLocalCleanupResult(deleted_class=True)

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
        *,
        extraction_source: str = "heuristic",
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
                extraction_source=sanitize_extraction_source(extraction_source),
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
    for token, label in INTAKE_PATTERNS.items():
        if token in lowered:
            add_entity("intake", label, 0.75, f"Mentioned intake pattern '{token}'.")
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

    if re.search(r"\b(i|me|my|mine|myself)\b", lowered):
        add_entity("person", "I", 0.95, "First-person reference in journal entry.")

    for role in KINSHIP_TITLES:
        if re.search(rf"\b{re.escape(role)}\b", lowered):
            add_entity("person", role, 0.8, f"Mentioned person role '{role}'.")

    for candidate in extract_case_sensitive_phrase(
        r"\b(?:with|to|texted|called|argued with|talked to|working with|met with|debriefed with)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
        text,
    ):
        if is_valid_person_candidate(candidate):
            add_entity("person", candidate, 0.82, f"Named person mention '{candidate}'.")
    for candidate in extract_phrase(
        r"\b(?:working with|met with|debriefed with|argued with|talked to|texted|called)\s+([a-z][a-z]+)\b",
        lowered,
    ):
        if is_valid_person_candidate(candidate):
            add_entity("person", candidate, 0.72, f"Contextual person mention '{candidate}'.")
    non_person_canonical_names = {
        entity.canonical_name
        for entity in entity_index.values()
        if entity.entity_type != "person"
    }
    for candidate in extract_case_sensitive_phrase(
        rf"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:{'|'.join(PERSON_ACTION_TERMS)})\b",
        text,
    ):
        if is_valid_person_candidate(candidate) and normalize_name(candidate) not in non_person_canonical_names:
            add_entity("person", candidate, 0.76, f"Action-linked person mention '{candidate}'.")
    for candidate in extract_case_sensitive_phrase(
        r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+and\s+(?:I|i)\b",
        text,
    ):
        if is_valid_person_candidate(candidate) and normalize_name(candidate) not in non_person_canonical_names:
            add_entity("person", candidate, 0.78, f"Co-mention with the current user '{candidate}'.")

    for candidate in extract_phrase(r"\b(?:at|in|to)\s+the\s+([a-z][a-z\s]{2,30})", lowered):
        if candidate in PLACE_PATTERNS or candidate in CONTEXT_PATTERNS:
            entity_type = "place" if candidate in PLACE_PATTERNS else "context"
            add_entity(entity_type, candidate, 0.64, f"Derived from location phrase '{candidate}'.")

    for candidate in extract_phrase(
        r"\bworking on\s+([a-z0-9][a-z0-9-]*(?:\s+(?!(?:with|because|after|before|and|but)\b)[a-z0-9][a-z0-9-]*){0,3})",
        lowered,
    ):
        if is_valid_project_candidate(candidate):
            add_entity("project", candidate, 0.68, f"Derived from 'working on {candidate}'.")
    for candidate in extract_phrase(
        r"(?:project|app|product)['\"]?\s+(?:refers?\s+to|is|was|called|named)\s+([a-z0-9][a-z0-9-]{1,30})",
        lowered,
    ):
        if is_valid_project_candidate(candidate):
            add_entity("project", candidate, 0.84, f"Derived from explicit project reference '{candidate}'.")
    for candidate in extract_phrase(
        r"(?:last project|current project|this project)['\"]?\s+(?:is|was|refers?\s+to|means|i'?m\s+referring\s+to|referring\s+to)\s+([a-z0-9][a-z0-9-]{1,30})",
        lowered,
    ):
        if is_valid_project_candidate(candidate):
            add_entity("project", candidate, 0.86, f"Derived from project alias reference '{candidate}'.")

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

        intakes = [entity for entity in sentence_entities if entity.entity_type == "intake"]
        for source_entity in intakes:
            for target_entity in impacted:
                add_relationship(source_entity, target_entity, "affected", 0.66, f"Intake linked to state in '{sentence}'.")

        goals = [entity for entity in sentence_entities if entity.entity_type == "goal"]
        habits = [entity for entity in sentence_entities if entity.entity_type == "habit"]
        if any(token in sentence_lower for token in NEGATIVE_HABIT_TERMS + ("ashamed", "guilty")):
            for habit in habits:
                for goal in goals:
                    add_relationship(habit, goal, "conflicts_with", 0.74, f"Negative habit signal conflicts with goal in '{sentence}'.")

        people = [entity for entity in sentence_entities if entity.entity_type == "person"]
        moods = [entity for entity in sentence_entities if entity.entity_type == "mood"]
        health_states = [entity for entity in sentence_entities if entity.entity_type == "health_state"]
        projects = [entity for entity in sentence_entities if entity.entity_type == "project"]
        organizations = [entity for entity in sentence_entities if entity.entity_type == "organization"]
        feeling_targets = [
            entity
            for entity in sentence_entities
            if entity.entity_type in {"person", "project", "organization", "context", "place", "goal", "habit", "intake"}
        ]
        for person in people:
            for mood in moods:
                add_relationship(person, mood, "experienced", 0.78, f"Person experienced mood in '{sentence}'.")
            for health_state in health_states:
                add_relationship(person, health_state, "experienced", 0.74, f"Person experienced health state in '{sentence}'.")
            if (moods or health_states) and any(token in sentence_lower for token in EMOTION_TARGET_TERMS):
                for target in feeling_targets:
                    if target.canonical_name == person.canonical_name:
                        continue
                    add_relationship(
                        person,
                        target,
                        "felt_about",
                        0.77,
                        f"Person felt a state about target in '{sentence}'.",
                    )
        if people and intakes:
            intake_relationship_type = None
            intake_confidence = 0.63
            if any(token in sentence_lower for token in INTAKE_AVOIDANCE_TERMS):
                intake_relationship_type = "avoided"
                intake_confidence = 0.82
            elif any(token in sentence_lower for token in INTAKE_USE_TERMS):
                intake_relationship_type = "used"
                intake_confidence = 0.8
            elif any(token in sentence_lower for token in INTAKE_CONSUMPTION_TERMS) or any(
                person.canonical_name == CURRENT_USER_CANONICAL_NAME for person in people
            ):
                intake_relationship_type = "consumed"
                intake_confidence = 0.72
            if intake_relationship_type is not None:
                for person in people:
                    for intake in intakes:
                        add_relationship(
                            person,
                            intake,
                            intake_relationship_type,
                            intake_confidence,
                            f"Person {intake_relationship_type.replace('_', ' ')} intake in '{sentence}'.",
                        )

        if any(token in sentence_lower for token in SPENT_TIME_TERMS) and len(people) >= 2:
            for index, source_person in enumerate(people):
                for target_person in people[index + 1 :]:
                    add_relationship(
                        source_person,
                        target_person,
                        "spent_time_with",
                        0.8,
                        f"Social time together in '{sentence}'.",
                    )
        elif (
            any(token in sentence_lower for token in INTERACTION_TERMS)
            or ((projects or organizations) and len(people) >= 2 and " with " in f" {sentence_lower} ")
        ) and len(people) >= 2:
            for index, source_person in enumerate(people):
                for target_person in people[index + 1 :]:
                    add_relationship(
                        source_person,
                        target_person,
                        "interacted_with",
                        0.76,
                        f"Interaction between people in '{sentence}'.",
                    )

        if any(token in sentence_lower for token in WORK_ACTIVITY_TERMS) and projects and people:
            for person in people:
                for project in projects:
                    add_relationship(
                        person,
                        project,
                        "worked_on",
                        0.8,
                        f"Work activity linked person to project in '{sentence}'.",
                    )

        if any(token in sentence_lower for token in BLOCKED_BY_TERMS):
            blockers = [
                entity
                for entity in sentence_entities
                if entity.entity_type in {"person", "organization", "context", "place", "health_state", "intake"}
            ]
            blocked_entities = [*projects, *goals, *habits] or people
            for blocked_entity in blocked_entities:
                for blocker in blockers:
                    if blocked_entity.canonical_name == blocker.canonical_name:
                        continue
                    add_relationship(
                        blocked_entity,
                        blocker,
                        "blocked_by",
                        0.79,
                        f"Blocked-by phrase in '{sentence}'.",
                    )

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
                extraction_source="heuristic",
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


def normalize_extraction(entry: JournalEntryRecord, extraction: GraphExtraction) -> GraphExtraction:
    normalized_entities: dict[tuple[str, str], ExtractedEntity] = {}
    canonical_name_map: dict[str, str] = {}
    has_first_person_reference = bool(re.search(r"\b(i|me|my|mine|myself)\b", entry.journal_entry.lower()))

    for entity in extraction.entities:
        original_entity_name = entity.name
        original_entity_canonical_name = entity.canonical_name
        entity_type = sanitize_entity_type(entity.entity_type)
        if entity_type is None:
            continue
        if entity_type == "person" and (
            is_placeholder_person_reference(entity.name)
            or is_placeholder_person_reference(entity.canonical_name)
        ):
            if not has_first_person_reference:
                continue
            entity = ExtractedEntity(
                entity_type="person",
                name="I",
                canonical_name=CURRENT_USER_CANONICAL_NAME,
                confidence=max(entity.confidence, 0.9),
                evidence="Normalized placeholder author reference to the current user because the journal entry is first-person.",
                aliases=["I", entity.name],
                needs_clarification=False,
                resolution_notes=None,
                candidate_canonical_name=None,
            )
        canonical_name, aliases, needs_clarification, resolution_notes, candidate_canonical_name = canonicalize_entity(
            entry.user_id,
            entity_type,
            entity.name or entity.canonical_name,
        )
        display_name_source = entity.name.strip() or display_name_from_canonical(canonical_name)
        if resolution_notes and resolution_notes.startswith("Applied user clarification"):
            display_name_source = display_name_from_canonical(canonical_name)
        display_name = normalize_free_text(display_name_source)
        entity_key = (entity_type, canonical_name)
        current = normalized_entities.get(entity_key)
        normalized_entity = ExtractedEntity(
            entity_type=entity_type,
            name=display_name,
            canonical_name=canonical_name,
            confidence=entity.confidence,
            evidence=normalize_free_text(entity.evidence),
            aliases=sorted({*aliases, *[alias.strip() for alias in entity.aliases if alias.strip()], display_name}),
            needs_clarification=entity.needs_clarification or needs_clarification,
            resolution_notes=entity.resolution_notes or resolution_notes,
            candidate_canonical_name=(
                normalize_name(entity.candidate_canonical_name)
                if entity.candidate_canonical_name
                else candidate_canonical_name
            ),
        )
        if current is None:
            normalized_entities[entity_key] = normalized_entity
        else:
            normalized_entities[entity_key] = ExtractedEntity(
                entity_type=current.entity_type,
                name=current.name if len(current.name) >= len(normalized_entity.name) else normalized_entity.name,
                canonical_name=current.canonical_name,
                confidence=max(current.confidence, normalized_entity.confidence),
                evidence=current.evidence if len(current.evidence) >= len(normalized_entity.evidence) else normalized_entity.evidence,
                aliases=sorted({*current.aliases, *normalized_entity.aliases}),
                needs_clarification=current.needs_clarification or normalized_entity.needs_clarification,
                resolution_notes=current.resolution_notes or normalized_entity.resolution_notes,
                candidate_canonical_name=current.candidate_canonical_name or normalized_entity.candidate_canonical_name,
            )
        canonical_name_map[original_entity_canonical_name] = canonical_name
        canonical_name_map[normalize_name(original_entity_name)] = canonical_name
        canonical_name_map[entity.canonical_name] = canonical_name
        canonical_name_map[normalize_name(entity.name)] = canonical_name

    if has_first_person_reference and ("person", CURRENT_USER_CANONICAL_NAME) not in normalized_entities:
        normalized_entities[("person", CURRENT_USER_CANONICAL_NAME)] = ExtractedEntity(
            entity_type="person",
            name="Self",
            canonical_name=CURRENT_USER_CANONICAL_NAME,
            confidence=0.98,
            evidence="Added current user entity from first-person journal language.",
            aliases=["I", "me", "my", "self"],
            needs_clarification=False,
            resolution_notes=None,
            candidate_canonical_name=None,
        )

    known_canonical_names = {entity.canonical_name for entity in normalized_entities.values()}
    entity_type_by_canonical_name = {
        entity.canonical_name: entity.entity_type
        for entity in normalized_entities.values()
    }

    def normalize_relationship_semantics(
        *,
        source_canonical_name: str,
        target_canonical_name: str,
        relationship_type: str,
    ) -> tuple[str, str, str]:
        source_type = entity_type_by_canonical_name.get(source_canonical_name)
        target_type = entity_type_by_canonical_name.get(target_canonical_name)

        if relationship_type == "affected" and source_type == "person" and target_type in {"mood", "health_state"}:
            return source_canonical_name, target_canonical_name, "experienced"

        if relationship_type == "about":
            if source_type == "person" and target_type in {"mood", "health_state"}:
                return source_canonical_name, target_canonical_name, "experienced"
            if source_type in {"mood", "health_state"} and target_type == "person":
                return target_canonical_name, source_canonical_name, "experienced"
            if source_type == "person" and target_type == "project":
                return source_canonical_name, target_canonical_name, "worked_on"
            if source_type == "project" and target_type == "person":
                return target_canonical_name, source_canonical_name, "worked_on"
            if source_type == "person" and target_type == "person":
                return source_canonical_name, target_canonical_name, "interacted_with"
            if source_type in {"context", "project", "place"} and target_type in {"mood", "health_state"}:
                return source_canonical_name, target_canonical_name, "affected"
            if source_type in {"mood", "health_state"} and target_type in {"context", "project", "place"}:
                return target_canonical_name, source_canonical_name, "affected"
        if relationship_type in {"consumed", "used", "avoided"} and source_type == "person" and target_type == "intake":
            return source_canonical_name, target_canonical_name, relationship_type
        if relationship_type == "felt_about":
            if source_type in {"mood", "health_state"} and target_type == "person":
                return target_canonical_name, source_canonical_name, "experienced"
            if source_type == "person" and target_type in {"project", "organization", "context", "place", "goal", "habit", "person", "intake"}:
                return source_canonical_name, target_canonical_name, "felt_about"
        if relationship_type == "spent_time_with" and source_type == target_type == "person":
            return source_canonical_name, target_canonical_name, "spent_time_with"
        if relationship_type == "blocked_by" and source_type in {"project", "goal", "habit", "person"}:
            return source_canonical_name, target_canonical_name, "blocked_by"

        return source_canonical_name, target_canonical_name, relationship_type

    normalized_relationships: dict[tuple[str, str, str], ExtractedRelationship] = {}
    for relationship in extraction.relationships:
        source_canonical_name = canonical_name_map.get(
            normalize_name(relationship.source_canonical_name),
            canonical_name_map.get(relationship.source_canonical_name, relationship.source_canonical_name),
        )
        target_canonical_name = canonical_name_map.get(
            normalize_name(relationship.target_canonical_name),
            canonical_name_map.get(relationship.target_canonical_name, relationship.target_canonical_name),
        )
        if source_canonical_name != "observation" and source_canonical_name not in known_canonical_names:
            continue
        if target_canonical_name != "observation" and target_canonical_name not in known_canonical_names:
            continue
        (
            source_canonical_name,
            target_canonical_name,
            normalized_relationship_type,
        ) = normalize_relationship_semantics(
            source_canonical_name=source_canonical_name,
            target_canonical_name=target_canonical_name,
            relationship_type=sanitize_relationship_type(relationship.relationship_type),
        )
        relationship_key = (
            source_canonical_name,
            target_canonical_name,
            normalized_relationship_type,
        )
        current = normalized_relationships.get(relationship_key)
        normalized_relationship = ExtractedRelationship(
            source_canonical_name=source_canonical_name,
            target_canonical_name=target_canonical_name,
            relationship_type=relationship_key[2],
            confidence=relationship.confidence,
            evidence=normalize_free_text(relationship.evidence),
            extraction_source=sanitize_extraction_source(relationship.extraction_source),
        )
        if current is None or normalized_relationship.confidence > current.confidence:
            normalized_relationships[relationship_key] = normalized_relationship

    project_name_map: dict[str, str] = {}
    for entity in normalized_entities.values():
        if entity.entity_type != "project":
            continue
        project_name_map[entity.canonical_name] = entity.canonical_name
        project_name_map[normalize_name(entity.name)] = entity.canonical_name
        for alias in entity.aliases:
            project_name_map[normalize_name(alias)] = entity.canonical_name

    def extract_project_alias_targets(pattern: str) -> list[str]:
        return [
            project_name_map.get(normalize_name(match), normalize_name(match))
            for match in re.findall(pattern, entry.journal_entry.lower())
            if project_name_map.get(normalize_name(match), normalize_name(match)) in known_canonical_names
        ]

    current_projects = extract_project_alias_targets(
        r"(?:this|current) project['\"]?\s+(?:is|was|refers?\s+to|means|i'?m\s+referring\s+to|referring\s+to)\s+([a-z0-9][a-z0-9-]{1,30})"
    )
    previous_projects = extract_project_alias_targets(
        r"(?:last|previous|prior) project['\"]?\s+(?:is|was|refers?\s+to|means|i'?m\s+referring\s+to|referring\s+to)\s+([a-z0-9][a-z0-9-]{1,30})"
    )
    if current_projects and previous_projects:
        for previous_project in previous_projects:
            for current_project in current_projects:
                if previous_project == current_project:
                    continue
                for relationship_key in (
                    (previous_project, current_project, "precedes"),
                    (current_project, previous_project, "precedes"),
                    (previous_project, current_project, "followed"),
                    (current_project, previous_project, "followed"),
                ):
                    normalized_relationships.pop(relationship_key, None)
                normalized_relationships[(previous_project, current_project, "precedes")] = ExtractedRelationship(
                    source_canonical_name=previous_project,
                    target_canonical_name=current_project,
                    relationship_type="precedes",
                    confidence=0.97,
                    evidence="Explicit project chronology: 'last/previous project' occurs before 'this/current project'.",
                    extraction_source="normalized",
                )
                normalized_relationships[(current_project, previous_project, "followed")] = ExtractedRelationship(
                    source_canonical_name=current_project,
                    target_canonical_name=previous_project,
                    relationship_type="followed",
                    confidence=0.97,
                    evidence="Explicit project chronology: 'this/current project' follows the 'last/previous project'.",
                    extraction_source="normalized",
                )

    normalized_summary = normalize_free_text(extraction.summary) if extraction.summary.strip() else build_episode_summary(entry)
    return GraphExtraction(
        summary=normalized_summary,
        entities=list(normalized_entities.values()),
        relationships=list(normalized_relationships.values()),
    )


def extract_graph_with_model(entry: JournalEntryRecord) -> GraphExtraction:
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0).with_structured_output(GraphExtraction)
    prompt = "\n".join(
        [
            "Extract a compact but personally useful knowledge graph from this journal entry.",
            "Use only entity types: person, organization, place, context, mood, project, habit, goal, intake, health_state.",
            "First-person pronouns always refer to the journal author and should map to the current user, not to an unknown person.",
            "Never create person entities named unknown, unnamed, author, or user.",
            "Use organization for companies, teams, employers, clients, or institutions when they are not the project itself.",
            "Use intake for consumed or body-input items like alcohol, weed, caffeine, medication, or high-sugar days.",
            "Prefer specific relationships over generic ones.",
            "Use experienced for person-to-mood or person-to-health_state links.",
            "Use worked_on for person-to-project work relationships.",
            "Use interacted_with for person-to-person social or collaborative contact.",
            "Use spent_time_with for softer social time together.",
            "Use consumed or used for person-to-intake links when someone drinks, eats, smokes, vapes, takes, or otherwise uses something.",
            "Use avoided for explicit restraint or sobriety around an intake.",
            "Use felt_about when a person expresses a mood or health state about a person, project, or context.",
            "Use blocked_by for obstacles that block a person, goal, habit, or project.",
            "Use followed for clear succession where one project or context came after another.",
            "Use only relationship types: affected, supported, conflicts_with, led_up_to, triggered_by, precedes, followed, causes, recurs, about, contributed_to, experienced, interacted_with, spent_time_with, worked_on, felt_about, blocked_by, consumed, used, avoided.",
            "Canonicalize aliases when they likely refer to the same thing, for example Josh and Joshua.",
            "If an alias merge is plausible but uncertain, set needs_clarification=true and explain why in resolution_notes.",
            "When uncertain, keep the raw name as the entity itself and put the suggested merge target in candidate_canonical_name.",
            "Return concise evidence grounded in the journal text or biometric payload. Do not invent entities.",
            f"Journal entry: {entry.journal_entry}",
            f"Goals: {', '.join(entry.goals) if entry.goals else 'None provided'}",
            f"Sleep hours: {entry.sleep_hours if entry.sleep_hours is not None else 'unknown'}",
            f"HRV ms: {entry.hrv_ms if entry.hrv_ms is not None else 'unknown'}",
            f"Steps: {entry.steps if entry.steps is not None else 'unknown'}",
        ]
    )
    return llm.invoke(prompt)


def extract_graph(entry: JournalEntryRecord) -> GraphExtraction:
    raw_extraction = extract_graph_with_model(entry) if os.getenv("OPENAI_API_KEY") else heuristic_extract_graph(entry)
    return normalize_extraction(entry, raw_extraction)


class GraphProjector:
    def __init__(self, base_url: str | None = None, username: str | None = None, password: str | None = None) -> None:
        self.base_url = (base_url or os.getenv("NEO4J_HTTP_URL") or "http://127.0.0.1:7474").rstrip("/")
        self.username = username or os.getenv("NEO4J_USERNAME") or "neo4j"
        self.password = resolve_neo4j_password(password)

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
        return extract_graph(entry)

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

    def list_source_record_ids_for_entity(
        self,
        *,
        user_id: str,
        entity_type: str,
        canonical_name: str,
    ) -> list[str]:
        try:
            result = self._query(
                """
                MATCH (o:Observation {user_id: $user_id})-[:OBSERVED]->(e:Entity {user_id: $user_id, entity_type: $entity_type, canonical_name: $canonical_name})
                RETURN DISTINCT o.source_record_id AS source_record_id
                ORDER BY source_record_id
                """,
                {
                    "user_id": user_id,
                    "entity_type": entity_type,
                    "canonical_name": canonical_name,
                },
            )
        except RuntimeError:
            return []
        rows = result.get("results", [{}])[0].get("data", [])
        source_record_ids: list[str] = []
        for row in rows:
            values = row.get("row", [])
            if values and values[0]:
                source_record_ids.append(str(values[0]))
        return source_record_ids

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

        if is_current_user_reference(entity.name) or is_current_user_reference(entity.canonical_name):
            return ExtractedEntity(
                entity_type=entity.entity_type,
                name=display_name_from_canonical(CURRENT_USER_CANONICAL_NAME).title(),
                canonical_name=CURRENT_USER_CANONICAL_NAME,
                confidence=entity.confidence,
                evidence=entity.evidence,
                aliases=sorted(
                    {
                        alias.strip()
                        for alias in [entity.name, *entity.aliases, entity.canonical_name]
                        if alias.strip()
                    }
                ),
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
        prepared_entity_map: dict[tuple[str, str], ExtractedEntity] = {}
        canonical_name_map: dict[str, str] = {}
        for entity in extraction.entities:
            prepared = self._prepare_entity_for_storage(entry, entity, existing_people)
            canonical_name_map[entity.canonical_name] = prepared.canonical_name
            canonical_name_map[normalize_name(entity.name)] = prepared.canonical_name
            entity_key = (prepared.entity_type, prepared.canonical_name)
            current = prepared_entity_map.get(entity_key)
            if current is None:
                prepared_entity_map[entity_key] = prepared
                continue
            prepared_entity_map[entity_key] = ExtractedEntity(
                entity_type=current.entity_type,
                name=current.name if len(current.name) >= len(prepared.name) else prepared.name,
                canonical_name=current.canonical_name,
                confidence=max(current.confidence, prepared.confidence),
                evidence=current.evidence if len(current.evidence) >= len(prepared.evidence) else prepared.evidence,
                aliases=sorted({*current.aliases, *prepared.aliases}),
                needs_clarification=current.needs_clarification or prepared.needs_clarification,
                resolution_notes=current.resolution_notes or prepared.resolution_notes,
                candidate_canonical_name=current.candidate_canonical_name or prepared.candidate_canonical_name,
            )

        prepared_relationship_map: dict[tuple[str, str, str], ExtractedRelationship] = {}
        for relationship in extraction.relationships:
            prepared_relationship = ExtractedRelationship(
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
                extraction_source=sanitize_extraction_source(relationship.extraction_source),
            )
            relationship_key = (
                prepared_relationship.source_canonical_name,
                prepared_relationship.target_canonical_name,
                prepared_relationship.relationship_type,
            )
            current = prepared_relationship_map.get(relationship_key)
            if current is None or prepared_relationship.confidence > current.confidence:
                prepared_relationship_map[relationship_key] = prepared_relationship
        return GraphExtraction(
            summary=extraction.summary,
            entities=list(prepared_entity_map.values()),
            relationships=list(prepared_relationship_map.values()),
        )

    def project(self, job: ProjectionJobRecord, entry: JournalEntryRecord) -> None:
        extraction = self.prepare_extraction(entry, self.extract(entry))
        for entity in extraction.entities:
            if not entity.needs_clarification or not entity.aliases:
                continue
            raw_name = entity.name
            candidate_canonical_name = entity.candidate_canonical_name or entity.canonical_name
            if (
                entity.entity_type == "person"
                and (
                    is_placeholder_person_reference(raw_name)
                    or is_placeholder_person_reference(candidate_canonical_name)
                    or entity.canonical_name == CURRENT_USER_CANONICAL_NAME
                )
            ):
                continue
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
                    r.confidence_bucket = $confidence_bucket,
                    r.evidence = $evidence,
                    r.extraction_source = $extraction_source,
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
                    "confidence_bucket": confidence_bucket_for_confidence(entity.confidence),
                    "evidence": entity.evidence,
                    "extraction_source": "system",
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
                    r.confidence_bucket = $confidence_bucket,
                    r.evidence = $evidence,
                    r.extraction_source = $extraction_source,
                    r.provenance = $provenance
                """,
                {
                    "source_key": known_entities[relation.source_canonical_name]["key"],
                    "target_key": known_entities[relation.target_canonical_name]["key"],
                    "source_record_id": entry.id,
                    "observation_id": observation_id,
                    "confidence": relation.confidence,
                    "confidence_bucket": confidence_bucket_for_confidence(relation.confidence),
                    "evidence": relation.evidence,
                    "extraction_source": sanitize_extraction_source(relation.extraction_source),
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

    def delete_user_data(self, user_id: str) -> GraphUserCleanupResult:
        result = self._query(
            """
            OPTIONAL MATCH (n {user_id: $user_id})
            OPTIONAL MATCH (n)-[r]-()
            WITH [node IN collect(DISTINCT n) WHERE node IS NOT NULL] AS nodes,
                 [relationship IN collect(DISTINCT r) WHERE relationship IS NOT NULL] AS relationships
            WITH nodes,
                 size([node IN nodes WHERE 'Observation' IN labels(node)]) AS deleted_observations,
                 size([node IN nodes WHERE 'Entity' IN labels(node)]) AS deleted_entities,
                 size(relationships) AS deleted_relationships
            FOREACH (node IN nodes | DETACH DELETE node)
            RETURN deleted_observations, deleted_entities, deleted_relationships
            """,
            {"user_id": user_id},
        )
        rows = result.get("results", [{}])[0].get("data", [])
        if not rows:
            return GraphUserCleanupResult(
                deleted_observations=0,
                deleted_entities=0,
                deleted_relationships=0,
            )
        deleted_observations, deleted_entities, deleted_relationships = rows[0].get("row", [0, 0, 0])
        return GraphUserCleanupResult(
            deleted_observations=int(deleted_observations),
            deleted_entities=int(deleted_entities),
            deleted_relationships=int(deleted_relationships),
        )

    def delete_local_data(self) -> GraphLocalCleanupResult:
        result = self._query(
            """
            OPTIONAL MATCH (n)
            WHERE 'Observation' IN labels(n) OR 'Entity' IN labels(n)
            OPTIONAL MATCH (n)-[r]-()
            WITH [node IN collect(DISTINCT n) WHERE node IS NOT NULL] AS nodes,
                 [relationship IN collect(DISTINCT r) WHERE relationship IS NOT NULL] AS relationships
            WITH nodes,
                 size([node IN nodes WHERE 'Observation' IN labels(node)]) AS deleted_observations,
                 size([node IN nodes WHERE 'Entity' IN labels(node)]) AS deleted_entities,
                 size(relationships) AS deleted_relationships
            FOREACH (node IN nodes | DETACH DELETE node)
            RETURN deleted_observations, deleted_entities, deleted_relationships
            """
        )
        rows = result.get("results", [{}])[0].get("data", [])
        if not rows:
            return GraphLocalCleanupResult(
                deleted_observations=0,
                deleted_entities=0,
                deleted_relationships=0,
            )
        deleted_observations, deleted_entities, deleted_relationships = rows[0].get("row", [0, 0, 0])
        return GraphLocalCleanupResult(
            deleted_observations=int(deleted_observations),
            deleted_entities=int(deleted_entities),
            deleted_relationships=int(deleted_relationships),
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


def process_pending_projection_jobs(
    *,
    limit: int = 10,
    user_id: str | None = None,
    projection_types: tuple[str, ...] | None = None,
) -> ProjectionRunResult:
    jobs = list_pending_projection_jobs(limit=limit, user_id=user_id, projection_types=projection_types)
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


def reproject_entry_artifacts(
    entry: JournalEntryRecord,
    jobs: list[ProjectionJobRecord],
) -> None:
    delete_derived_artifacts(entry, jobs)
    weaviate = WeaviateProjector()
    graph = GraphProjector()
    for job in jobs:
        if job.projection_type.startswith("weaviate_"):
            weaviate.project(job, entry)
        elif job.projection_type == "neo4j_knowledge_graph":
            graph.project(job, entry)
        else:  # pragma: no cover - guarded by projection type definitions
            raise RuntimeError(f"Unsupported projection type {job.projection_type}")
