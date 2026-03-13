from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from midas.core.memory import (
    JournalEntryRecord,
    ClarificationTaskRecord,
    list_clarification_tasks_for_user,
    list_journal_entries_for_user,
    list_projection_jobs_for_user,
)
from midas.core.projections import GraphProjector, WeaviateProjector


@dataclass(frozen=True)
class ReviewFinding:
    title: str
    detail: str
    evidence: list[str]


@dataclass(frozen=True)
class ReviewStat:
    label: str
    value: str


@dataclass(frozen=True)
class WeeklyReviewResult:
    summary: str
    generated_at: datetime
    window_days: int
    findings: list[ReviewFinding]
    stats: list[ReviewStat]
    entries: list[JournalEntryRecord]
    memory_highlights: list[dict[str, Any]]
    graph_nodes: list[dict[str, Any]]
    graph_relationships: list[dict[str, Any]]
    clarifications: list[ClarificationTaskRecord]
    warnings: list[str]


def _display_name(node: dict[str, Any]) -> str:
    properties = dict(node.get("properties", {}))
    return (
        str(properties.get("display_name"))
        or str(properties.get("canonical_name"))
        or str(properties.get("summary"))
        or str(node.get("id", ""))
    )


def _format_average(values: list[float], suffix: str) -> str:
    if not values:
        return "n/a"
    return f"{sum(values) / len(values):.1f}{suffix}"


def build_weekly_review(*, user_id: str, window_days: int = 7) -> WeeklyReviewResult:
    generated_at = datetime.now(UTC)
    cutoff = generated_at - timedelta(days=window_days)
    all_entries = list_journal_entries_for_user(user_id)
    entries = [entry for entry in all_entries if entry.created_at >= cutoff]
    warnings: list[str] = []

    weaviate = WeaviateProjector()
    graph = GraphProjector()

    memory_highlights: list[dict[str, Any]] = []
    graph_nodes: dict[str, dict[str, Any]] = {}
    graph_relationships: dict[str, dict[str, Any]] = {}

    for entry in entries:
        jobs = list_projection_jobs_for_user(user_id, source_record_id=entry.id)
        for job in jobs:
            if not job.projection_type.startswith("weaviate_") or job.status != "completed":
                continue
            artifact = weaviate.fetch_object(job.id)
            if artifact is None:
                warnings.append(f"Weaviate artifact missing for {job.id}")
                continue
            memory_highlights.append(
                {
                    "projection_job_id": job.id,
                    "object_id": str(artifact.get("id", job.id)),
                    "class_name": str(artifact.get("class", "")),
                    "content": dict(artifact.get("properties", {})).get("content"),
                    "url": weaviate.object_url(job.id),
                    "raw": artifact,
                }
            )

        try:
            observation = graph.fetch_observation(entry.id, user_id)
        except Exception:
            warnings.append(f"Neo4j observation unavailable for {entry.id}")
            continue

        for node in observation.get("nodes", []):
            graph_nodes[str(node.get("id"))] = node
        for relationship in observation.get("relationships", []):
            graph_relationships[str(relationship.get("id"))] = relationship

    clarifications = list_clarification_tasks_for_user(user_id, status="pending")

    goal_counter = Counter(goal for entry in entries for goal in entry.goals)
    memory_counter = Counter(
        str(dict(artifact.get("raw", {}).get("properties", {})).get("projection_type", "unknown"))
        for artifact in memory_highlights
    )
    relationship_counter = Counter(
        str(relationship.get("type", "")).lower()
        for relationship in graph_relationships.values()
        if str(relationship.get("type", "")).upper() != "OBSERVED"
    )
    entity_counter = Counter(
        _display_name(node)
        for node in graph_nodes.values()
        if "Observation" not in node.get("labels", [])
    )

    findings: list[ReviewFinding] = []
    if entries:
        findings.append(
            ReviewFinding(
                title="Recent journaling volume",
                detail=f"You logged {len(entries)} entries in the last {window_days} days.",
                evidence=[entry.journal_entry for entry in entries[:2]],
            )
        )
    if goal_counter:
        top_goals = ", ".join(goal for goal, _count in goal_counter.most_common(3))
        findings.append(
            ReviewFinding(
                title="Most active goals",
                detail=f"Your recent entries focused most on: {top_goals}.",
                evidence=[f"{goal}: {count} entries" for goal, count in goal_counter.most_common(3)],
            )
        )
    if relationship_counter:
        top_relationship = relationship_counter.most_common(1)[0]
        findings.append(
            ReviewFinding(
                title="Graph pattern",
                detail=f"The graph most often linked experiences through '{top_relationship[0]}' relationships.",
                evidence=[f"{name}: {count}" for name, count in relationship_counter.most_common(3)],
            )
        )
    if memory_counter:
        findings.append(
            ReviewFinding(
                title="Memory artifacts",
                detail="Weekly review is pulling from stored Weaviate artifacts instead of only raw journal text.",
                evidence=[f"{name}: {count}" for name, count in memory_counter.most_common(3)],
            )
        )
    if clarifications:
        findings.append(
            ReviewFinding(
                title="Pending clarifications",
                detail=f"There are {len(clarifications)} unresolved name or alias questions that can sharpen future graph extraction.",
                evidence=[task.prompt for task in clarifications[:3]],
            )
        )

    sleep_values = [entry.sleep_hours for entry in entries if entry.sleep_hours is not None]
    hrv_values = [entry.hrv_ms for entry in entries if entry.hrv_ms is not None]
    step_values = [float(entry.steps) for entry in entries if entry.steps is not None]
    stats = [
        ReviewStat(label="Entries", value=str(len(entries))),
        ReviewStat(label="Avg sleep", value=_format_average(sleep_values, "h")),
        ReviewStat(label="Avg HRV", value=_format_average(hrv_values, "ms")),
        ReviewStat(label="Avg steps", value=_format_average(step_values, "")),
        ReviewStat(label="Graph entities", value=str(len([node for node in graph_nodes.values() if "Observation" not in node.get("labels", [])]))),
        ReviewStat(label="Pending clarifications", value=str(len(clarifications))),
    ]

    top_entities = ", ".join(name for name, _count in entity_counter.most_common(3))
    if findings:
        summary_parts = [finding.detail for finding in findings[:3]]
    else:
        summary_parts = ["No recent review signals were found yet."]
    if top_entities:
        summary_parts.append(f"Most visible entities: {top_entities}.")
    summary = " ".join(summary_parts)

    return WeeklyReviewResult(
        summary=summary,
        generated_at=generated_at,
        window_days=window_days,
        findings=findings,
        stats=stats,
        entries=entries,
        memory_highlights=memory_highlights[:6],
        graph_nodes=list(graph_nodes.values()),
        graph_relationships=list(graph_relationships.values()),
        clarifications=clarifications,
        warnings=warnings,
    )
