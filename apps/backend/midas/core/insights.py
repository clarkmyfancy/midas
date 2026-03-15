from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from midas.core.memory import (
    list_clarification_tasks_for_user,
    list_journal_entries_for_user,
    list_projection_jobs_for_user,
)
from midas.core.projections import GraphProjector, WeaviateProjector
from midas.core.review import WEAVIATE_REVIEW_PREFERENCE


POSITIVE_STATE_NAMES = {"great", "pumped", "excited", "strong sleep", "high hrv"}
NEGATIVE_STATE_NAMES = {
    "anxious",
    "ashamed",
    "tired",
    "scattered",
    "irritable",
    "guilty",
    "overwhelmed",
    "wired",
    "drained",
    "resentful",
    "poor sleep",
    "low hrv",
    "burnout",
    "exhaustion",
    "low energy",
}
RELATIONSHIP_LABELS = {
    "blocked_by": "blocked by",
    "conflicts_with": "conflicts with",
    "worked_on": "worked on",
    "spent_time_with": "spent time with",
    "interacted_with": "interacted with",
    "experienced": "experienced",
    "affected": "affected",
    "consumed": "consumed",
    "used": "used",
    "avoided": "avoided",
    "precedes": "precedes",
    "followed": "followed",
}


@dataclass(frozen=True)
class InsightStat:
    label: str
    value: str


@dataclass(frozen=True)
class InsightCard:
    id: str
    category: str
    title: str
    summary: str
    severity: str
    confidence: float
    evidence: list[str]
    related_entities: list[str]
    source_types: list[str]


@dataclass(frozen=True)
class InsightSection:
    id: str
    title: str
    description: str
    cards: list[InsightCard]


@dataclass(frozen=True)
class InsightsResult:
    summary: str
    generated_at: datetime
    window_days: int
    sections: list[InsightSection]
    stats: list[InsightStat]
    warnings: list[str]


def _display_name_from_node(node: dict[str, Any]) -> str:
    properties = dict(node.get("properties", {}))
    raw_value = (
        properties.get("display_name")
        or properties.get("canonical_name")
        or properties.get("summary")
        or node.get("id", "")
    )
    return str(raw_value).replace("_", " ").strip()


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _severity_for_confidence(confidence: float) -> str:
    if confidence >= 0.85:
        return "high"
    if confidence >= 0.65:
        return "medium"
    return "low"


def _preferred_artifact_for_entry(
    *,
    user_id: str,
    entry_id: str,
    weaviate: WeaviateProjector,
    warnings: list[str],
) -> dict[str, Any] | None:
    jobs = list_projection_jobs_for_user(user_id, source_record_id=entry_id)
    preferred_artifact: dict[str, Any] | None = None
    preferred_rank = 10**6
    for job in jobs:
        if not job.projection_type.startswith("weaviate_") or job.status != "completed":
            continue
        artifact = weaviate.fetch_object(job.id)
        if artifact is None:
            warnings.append(f"Weaviate artifact missing for {job.id}")
            continue
        rank = WEAVIATE_REVIEW_PREFERENCE.get(job.projection_type, 100)
        if preferred_artifact is None or rank < preferred_rank:
            preferred_artifact = artifact
            preferred_rank = rank
    return preferred_artifact


def _build_attention_card(
    *,
    project_counter: Counter[str],
    organization_counter: Counter[str],
    context_counter: Counter[str],
    artifact_contents: list[str],
) -> InsightCard | None:
    primary_threads = [name for name, _count in project_counter.most_common(2)]
    if not primary_threads:
        primary_threads = [name for name, _count in organization_counter.most_common(2)]
    if not primary_threads:
        primary_threads = [name for name, _count in context_counter.most_common(2)]
    if not primary_threads:
        return None
    confidence = min(0.92, 0.58 + (0.08 * len(primary_threads)) + (0.04 * project_counter[primary_threads[0]]))
    return InsightCard(
        id="attention-orbit",
        category="patterns",
        title="Attention orbit",
        summary=(
            f"Your recent reflections keep circling around {', '.join(primary_threads)}, "
            "which suggests these are the main organizing threads in your current period rather than isolated mentions."
        ),
        severity=_severity_for_confidence(confidence),
        confidence=confidence,
        evidence=[
            *[f"{name}: {count} linked graph mentions" for name, count in project_counter.most_common(3)],
            *artifact_contents[:2],
        ][:4],
        related_entities=primary_threads,
        source_types=["postgres", "weaviate", "neo4j"],
    )


def _build_state_card(
    *,
    state_counter: Counter[str],
    sleep_values: list[float],
    hrv_values: list[float],
) -> InsightCard | None:
    if not state_counter:
        return None
    dominant_states = [name for name, _count in state_counter.most_common(3)]
    average_sleep = sum(sleep_values) / len(sleep_values) if sleep_values else None
    average_hrv = sum(hrv_values) / len(hrv_values) if hrv_values else None
    negative_hits = sum(count for name, count in state_counter.items() if name.lower() in NEGATIVE_STATE_NAMES)
    positive_hits = sum(count for name, count in state_counter.items() if name.lower() in POSITIVE_STATE_NAMES)
    if negative_hits > positive_hits:
        summary = (
            f"The emotional baseline in this window leans toward {', '.join(dominant_states)}, "
            "which makes the period look more like sustained strain than a one-off rough day."
        )
    else:
        summary = (
            f"The emotional baseline in this window leans toward {', '.join(dominant_states)}, "
            "which suggests more activation and forward motion than drag."
        )
    evidence = [f"{name}: {count} experienced links" for name, count in state_counter.most_common(4)]
    if average_sleep is not None:
        evidence.append(f"Average sleep: {average_sleep:.1f}h")
    if average_hrv is not None:
        evidence.append(f"Average HRV: {average_hrv:.1f}ms")
    confidence = min(0.94, 0.62 + (0.04 * state_counter[dominant_states[0]]))
    return InsightCard(
        id="state-baseline",
        category="patterns",
        title="State baseline",
        summary=summary,
        severity="high" if negative_hits > positive_hits else _severity_for_confidence(confidence),
        confidence=confidence,
        evidence=evidence[:4],
        related_entities=dominant_states,
        source_types=["postgres", "neo4j"],
    )


def _build_friction_card(
    *,
    blocked_counter: Counter[str],
    conflict_counter: Counter[str],
) -> InsightCard | None:
    if not blocked_counter and not conflict_counter:
        return None
    dominant_pair, dominant_count = (blocked_counter + conflict_counter).most_common(1)[0]
    summary = (
        f"The strongest repeated friction pattern is {dominant_pair}, which is showing up often enough "
        "to look structural rather than incidental."
    )
    confidence = min(0.95, 0.68 + (0.05 * dominant_count))
    evidence = [
        *[f"{pair}: {count} blocked-by links" for pair, count in blocked_counter.most_common(2)],
        *[f"{pair}: {count} conflict links" for pair, count in conflict_counter.most_common(2)],
    ][:4]
    related_entities = [part.strip() for part in dominant_pair.split(" -> ")]
    return InsightCard(
        id="friction-cluster",
        category="tensions",
        title="Friction cluster",
        summary=summary,
        severity="high",
        confidence=confidence,
        evidence=evidence,
        related_entities=related_entities,
        source_types=["neo4j", "postgres"],
    )


def _build_social_card(
    *,
    person_counter: Counter[str],
    conflict_counter: Counter[str],
    social_counter: Counter[str],
) -> InsightCard | None:
    if not person_counter:
        return None
    lead_person, lead_count = person_counter.most_common(1)[0]
    mixed_pairs = [pair for pair in conflict_counter if lead_person in pair]
    if mixed_pairs:
        summary = (
            f"{lead_person} appears as a repeated relationship anchor, and the graph shows both contact and tension around them. "
            "That usually means the dynamic is meaningful, not background noise."
        )
        evidence = [
            *[f"{pair}: {count} social links" for pair, count in social_counter.items() if lead_person in pair][:2],
            *[f"{pair}: {count} conflict links" for pair, count in conflict_counter.items() if lead_person in pair][:2],
        ]
        severity = "high"
        confidence = min(0.93, 0.68 + (0.04 * lead_count))
    else:
        summary = (
            f"{lead_person} is the most persistent person in your recent graph, which suggests this relationship is absorbing a large share of your attention."
        )
        evidence = [f"{pair}: {count} social links" for pair, count in social_counter.items() if lead_person in pair][:3]
        severity = "medium"
        confidence = min(0.88, 0.62 + (0.04 * lead_count))
    return InsightCard(
        id="social-dynamics",
        category="relationships",
        title="Social dynamics",
        summary=summary,
        severity=severity,
        confidence=confidence,
        evidence=evidence[:4],
        related_entities=[lead_person],
        source_types=["neo4j", "postgres"],
    )


def _build_intake_card(
    *,
    intake_counter: Counter[str],
    intake_effect_counter: Counter[str],
    intake_behavior_counter: Counter[str],
) -> InsightCard | None:
    if not intake_counter:
        return None
    lead_intake, lead_count = intake_counter.most_common(1)[0]
    summary = (
        f"{lead_intake} is not just present in the graph; it is showing up as part of the state picture, "
        "which makes it more plausible as a pattern variable than a background detail."
    )
    confidence = min(0.91, 0.64 + (0.05 * lead_count))
    evidence = [
        *[f"{pair}: {count} intake-to-state links" for pair, count in intake_effect_counter.most_common(2)],
        *[f"{pair}: {count} behavior links" for pair, count in intake_behavior_counter.most_common(2)],
    ][:4]
    return InsightCard(
        id="intake-signal",
        category="health",
        title="Intake signal",
        summary=summary,
        severity="medium",
        confidence=confidence,
        evidence=evidence,
        related_entities=[name for name, _count in intake_counter.most_common(3)],
        source_types=["neo4j", "weaviate", "postgres"],
    )


def _build_transition_card(*, transition_counter: Counter[str]) -> InsightCard | None:
    if not transition_counter:
        return None
    top_transition, top_count = transition_counter.most_common(1)[0]
    confidence = min(0.95, 0.7 + (0.04 * top_count))
    return InsightCard(
        id="transition-pattern",
        category="momentum",
        title="Transition pattern",
        summary=(
            f"The graph is carrying a stable succession signal around {top_transition}, "
            "which gives your recent work history a clearer arc rather than a set of disconnected projects."
        ),
        severity="medium",
        confidence=confidence,
        evidence=[f"{pair}: {count} succession links" for pair, count in transition_counter.most_common(3)],
        related_entities=[part.strip() for part in top_transition.split(" -> ")],
        source_types=["neo4j", "postgres"],
    )


def _build_question_card(*, pending_clarifications: int, weak_signal_count: int) -> InsightCard | None:
    if pending_clarifications <= 0 and weak_signal_count <= 0:
        return None
    evidence: list[str] = []
    if pending_clarifications > 0:
        evidence.append(f"{pending_clarifications} clarifications are still unresolved.")
    if weak_signal_count > 0:
        evidence.append(f"{weak_signal_count} lower-confidence graph edges were excluded by the current threshold.")
    confidence = 0.82 if pending_clarifications else 0.7
    return InsightCard(
        id="open-questions",
        category="blindspots",
        title="Open questions",
        summary=(
            "Some of the story is still ambiguous, so a portion of the deeper interpretation is being deliberately held back until names or weak links are resolved."
        ),
        severity="medium",
        confidence=confidence,
        evidence=evidence,
        related_entities=[],
        source_types=["postgres", "neo4j"],
    )


def build_insights(*, user_id: str, window_days: int = 30, confidence_threshold: float = 0.65) -> InsightsResult:
    generated_at = datetime.now(UTC)
    cutoff = generated_at - timedelta(days=window_days)
    entries = [entry for entry in list_journal_entries_for_user(user_id) if entry.created_at >= cutoff]
    warnings: list[str] = []
    weaviate = WeaviateProjector()
    graph = GraphProjector()

    graph_nodes: dict[str, dict[str, Any]] = {}
    graph_relationships: dict[str, dict[str, Any]] = {}
    node_name_by_id: dict[str, str] = {}
    person_counter: Counter[str] = Counter()
    project_counter: Counter[str] = Counter()
    organization_counter: Counter[str] = Counter()
    context_counter: Counter[str] = Counter()
    state_counter: Counter[str] = Counter()
    intake_counter: Counter[str] = Counter()
    blocked_counter: Counter[str] = Counter()
    conflict_counter: Counter[str] = Counter()
    social_counter: Counter[str] = Counter()
    transition_counter: Counter[str] = Counter()
    intake_effect_counter: Counter[str] = Counter()
    intake_behavior_counter: Counter[str] = Counter()
    artifact_contents: list[str] = []
    weak_signal_count = 0

    for entry in entries:
        artifact = _preferred_artifact_for_entry(
            user_id=user_id,
            entry_id=entry.id,
            weaviate=weaviate,
            warnings=warnings,
        )
        if artifact is not None:
            properties = dict(artifact.get("properties", {}))
            content = str(properties.get("content", "")).strip()
            if content:
                artifact_contents.append(content)
            for value in properties.get("projects", []) or []:
                project_counter[str(value).replace("_", " ")] += 1
            for value in properties.get("organizations", []) or []:
                organization_counter[str(value).replace("_", " ")] += 1
            for value in properties.get("contexts", []) or []:
                context_counter[str(value).replace("_", " ")] += 1
            for value in properties.get("moods", []) or []:
                state_counter[str(value).replace("_", " ")] += 1
            for value in properties.get("intakes", []) or []:
                intake_counter[str(value).replace("_", " ")] += 1

        try:
            observation = graph.fetch_observation(entry.id, user_id)
        except Exception:
            warnings.append(f"Neo4j observation unavailable for {entry.id}")
            continue

        for node in observation.get("nodes", []):
            node_id = str(node.get("id"))
            graph_nodes[node_id] = node
            node_name = _display_name_from_node(node)
            node_name_by_id[node_id] = node_name
            labels = {str(label) for label in node.get("labels", [])}
            properties = dict(node.get("properties", {}))
            canonical_name = str(properties.get("canonical_name", "")).replace("_", " ").strip().lower()
            if "Observation" in labels:
                continue
            if "Person" in labels and canonical_name != "self":
                person_counter[node_name] += 1
            elif "Project" in labels:
                project_counter[node_name] += 1
            elif "Organization" in labels:
                organization_counter[node_name] += 1
            elif "Context" in labels or "Place" in labels:
                context_counter[node_name] += 1
            elif "Mood" in labels or "HealthState" in labels:
                state_counter[node_name] += 1
            elif "Intake" in labels:
                intake_counter[node_name] += 1

        for relationship in observation.get("relationships", []):
            relationship_type = str(relationship.get("type", "")).upper()
            if relationship_type == "OBSERVED":
                graph_relationships[str(relationship.get("id"))] = relationship
                continue
            properties = dict(relationship.get("properties", {}))
            confidence = _safe_float(properties.get("confidence"))
            if confidence is not None and confidence < confidence_threshold:
                weak_signal_count += 1
                continue
            relationship_id = str(relationship.get("id"))
            graph_relationships[relationship_id] = relationship
            start_name = node_name_by_id.get(str(relationship.get("startNode")), str(relationship.get("startNode")))
            end_name = node_name_by_id.get(str(relationship.get("endNode")), str(relationship.get("endNode")))
            pair = f"{start_name} -> {end_name}"
            normalized_type = relationship_type.lower()
            if normalized_type == "blocked_by":
                blocked_counter[pair] += 1
            elif normalized_type == "conflicts_with":
                conflict_counter[pair] += 1
            elif normalized_type in {"interacted_with", "spent_time_with"}:
                social_counter[pair] += 1
            elif normalized_type in {"precedes", "followed"}:
                transition_counter[pair] += 1
            elif normalized_type == "affected":
                intake_effect_counter[pair] += 1
            elif normalized_type in {"consumed", "used", "avoided"}:
                intake_behavior_counter[f"{start_name} {RELATIONSHIP_LABELS.get(normalized_type, normalized_type)} {end_name}"] += 1
            elif normalized_type == "experienced" and "self" in start_name.lower():
                state_counter[end_name] += 1

    sleep_values = [entry.sleep_hours for entry in entries if entry.sleep_hours is not None]
    hrv_values = [entry.hrv_ms for entry in entries if entry.hrv_ms is not None]
    step_values = [float(entry.steps) for entry in entries if entry.steps is not None]
    clarifications = list_clarification_tasks_for_user(user_id, status="pending")

    sections: list[InsightSection] = []
    pattern_cards = [
        card
        for card in [
            _build_attention_card(
                project_counter=project_counter,
                organization_counter=organization_counter,
                context_counter=context_counter,
                artifact_contents=artifact_contents,
            ),
            _build_state_card(
                state_counter=state_counter,
                sleep_values=sleep_values,
                hrv_values=hrv_values,
            ),
        ]
        if card is not None
    ]
    if pattern_cards:
        sections.append(
            InsightSection(
                id="patterns",
                title="Patterns",
                description="The longer-running threads that keep structuring your recent reflections.",
                cards=pattern_cards,
            )
        )

    tension_cards = [
        card
        for card in [
            _build_friction_card(
                blocked_counter=blocked_counter,
                conflict_counter=conflict_counter,
            ),
            _build_intake_card(
                intake_counter=intake_counter,
                intake_effect_counter=intake_effect_counter,
                intake_behavior_counter=intake_behavior_counter,
            ),
        ]
        if card is not None
    ]
    if tension_cards:
        sections.append(
            InsightSection(
                id="tensions",
                title="Tensions",
                description="Where the graph suggests friction, strain, or destabilizing inputs.",
                cards=tension_cards,
            )
        )

    relationship_cards = [
        card
        for card in [
            _build_social_card(
                person_counter=person_counter,
                conflict_counter=conflict_counter,
                social_counter=social_counter,
            ),
            _build_transition_card(transition_counter=transition_counter),
        ]
        if card is not None
    ]
    if relationship_cards:
        sections.append(
            InsightSection(
                id="dynamics",
                title="Dynamics",
                description="How relationships, projects, and transitions are evolving across the window.",
                cards=relationship_cards,
            )
        )

    blindspot_card = _build_question_card(
        pending_clarifications=len(clarifications),
        weak_signal_count=weak_signal_count,
    )
    if blindspot_card is not None:
        sections.append(
            InsightSection(
                id="blindspots",
                title="Blind spots",
                description="What is still ambiguous enough that the system is treating it cautiously.",
                cards=[blindspot_card],
            )
        )

    total_cards = sum(len(section.cards) for section in sections)
    top_card = sections[0].cards[0] if sections and sections[0].cards else None
    if top_card is not None:
        summary = (
            f"Across the last {window_days} days, the strongest recurring signal is {top_card.title.lower()}: {top_card.summary}"
        )
    elif entries:
        summary = f"You have {len(entries)} recent entries, but not enough repeated structure yet for strong longitudinal synthesis."
    else:
        summary = "No recent entries were found, so there is not enough material yet to synthesize longitudinal insights."

    stats = [
        InsightStat(label="Entries", value=str(len(entries))),
        InsightStat(label="Insight cards", value=str(total_cards)),
        InsightStat(label="Graph edges", value=str(len([item for item in graph_relationships.values() if str(item.get("type", "")).upper() != "OBSERVED"]))),
        InsightStat(label="Pending clarifications", value=str(len(clarifications))),
        InsightStat(label="Avg sleep", value=f"{(sum(sleep_values) / len(sleep_values)):.1f}h" if sleep_values else "n/a"),
        InsightStat(label="Avg steps", value=f"{(sum(step_values) / len(step_values)):.0f}" if step_values else "n/a"),
    ]

    return InsightsResult(
        summary=summary,
        generated_at=generated_at,
        window_days=window_days,
        sections=sections,
        stats=stats,
        warnings=warnings,
    )
