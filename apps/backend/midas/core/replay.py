from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime

from midas.core.memory import (
    JournalEntryRecord,
    NEO4J_PROJECTION_TYPES,
    PROJECTION_TYPES,
    ProjectionJobRecord,
    WEAVIATE_PROJECTION_TYPES,
    list_projection_jobs_for_user,
    mark_projection_job_completed,
    mark_projection_job_failed,
)
from midas.core.projections import GraphProjector, WeaviateProjector

try:
    import psycopg
except ImportError:  # pragma: no cover - local fallback until env is synced
    psycopg = None


@dataclass(frozen=True)
class ReplaySelection:
    entries: list[JournalEntryRecord]
    projection_types: tuple[str, ...]


@dataclass(frozen=True)
class ReplayProjectionResult:
    selected_entries: int
    selected_jobs: int
    completed_jobs: int
    failed_jobs: int
    jobs: list[ProjectionJobRecord]


def resolve_replay_projection_types(target: str) -> tuple[str, ...]:
    normalized = target.strip().lower()
    if normalized == "all":
        return PROJECTION_TYPES
    if normalized == "weaviate":
        return WEAVIATE_PROJECTION_TYPES
    if normalized == "neo4j":
        return NEO4J_PROJECTION_TYPES
    raise ValueError(f"Unsupported replay target '{target}'")


def require_replay_db_uri() -> str:
    db_uri = os.getenv("POSTGRES_URI")
    if not db_uri:
        raise RuntimeError("POSTGRES_URI is required for replay tooling")
    if psycopg is None:
        raise RuntimeError("psycopg is required for replay tooling")
    return db_uri


def load_replay_entries(
    *,
    entry_id: str | None = None,
    user_id: str | None = None,
    all_users: bool = False,
) -> list[JournalEntryRecord]:
    if entry_id and all_users:
        raise ValueError("entry_id and all_users cannot be combined")
    if entry_id and user_id:
        where_clause = "WHERE id = %s AND user_id = %s"
        params: list[object] = [entry_id, user_id]
    elif entry_id:
        where_clause = "WHERE id = %s"
        params = [entry_id]
    elif user_id:
        where_clause = "WHERE user_id = %s"
        params = [user_id]
    elif all_users:
        where_clause = ""
        params = []
    else:
        raise ValueError("Provide entry_id, user_id, or all_users=True")

    query = f"""
        SELECT id, user_id, journal_entry, goals_json, thread_id, steps, sleep_hours, hrv_ms, source, created_at
        FROM journal_entries
        {where_clause}
        ORDER BY created_at ASC
    """

    with psycopg.connect(require_replay_db_uri()) as conn, conn.cursor() as cur:
        cur.execute(query, params)
        rows = cur.fetchall()

    entries: list[JournalEntryRecord] = []
    for row in rows:
        entries.append(
            JournalEntryRecord(
                id=row[0],
                user_id=row[1],
                journal_entry=row[2],
                goals=list(row[3] if isinstance(row[3], list) else json.loads(row[3])),
                thread_id=row[4],
                steps=row[5],
                sleep_hours=row[6],
                hrv_ms=row[7],
                source=row[8],
                created_at=row[9] if isinstance(row[9], datetime) else datetime.fromisoformat(str(row[9])),
            )
        )
    return entries


def build_replay_selection(
    *,
    target: str,
    entry_id: str | None = None,
    user_id: str | None = None,
    all_users: bool = False,
) -> ReplaySelection:
    return ReplaySelection(
        entries=load_replay_entries(entry_id=entry_id, user_id=user_id, all_users=all_users),
        projection_types=resolve_replay_projection_types(target),
    )


def replay_projection_scope(
    *,
    target: str,
    entry_id: str | None = None,
    user_id: str | None = None,
    all_users: bool = False,
    dry_run: bool = False,
) -> ReplayProjectionResult:
    selection = build_replay_selection(
        target=target,
        entry_id=entry_id,
        user_id=user_id,
        all_users=all_users,
    )

    selected_jobs = 0
    completed: list[ProjectionJobRecord] = []
    failed: list[ProjectionJobRecord] = []

    weaviate = None
    graph = None
    if not dry_run:
        if any(item in WEAVIATE_PROJECTION_TYPES for item in selection.projection_types):
            weaviate = WeaviateProjector()
        if any(item in NEO4J_PROJECTION_TYPES for item in selection.projection_types):
            graph = GraphProjector()

    for entry in selection.entries:
        jobs = [
            job
            for job in list_projection_jobs_for_user(entry.user_id, source_record_id=entry.id)
            if job.projection_type in selection.projection_types
        ]
        selected_jobs += len(jobs)
        if dry_run or not jobs:
            continue

        weaviate_jobs = [job for job in jobs if job.projection_type in WEAVIATE_PROJECTION_TYPES]
        graph_jobs = [job for job in jobs if job.projection_type in NEO4J_PROJECTION_TYPES]

        if weaviate and weaviate_jobs:
            try:
                weaviate.delete_objects([job.id for job in weaviate_jobs])
            except Exception as exc:
                for job in weaviate_jobs:
                    failed.append(mark_projection_job_failed(job.id, f"Replay failed before projection: {exc}"))
                weaviate_jobs = []

        if graph and graph_jobs:
            try:
                graph.delete_observation(entry.id, entry.user_id)
            except Exception as exc:
                for job in graph_jobs:
                    failed.append(mark_projection_job_failed(job.id, f"Replay failed before projection: {exc}"))
                graph_jobs = []

        for job in [*weaviate_jobs, *graph_jobs]:
            try:
                if weaviate and job.projection_type in WEAVIATE_PROJECTION_TYPES:
                    weaviate.project(job, entry)
                elif graph and job.projection_type in NEO4J_PROJECTION_TYPES:
                    graph.project(job, entry)
                else:  # pragma: no cover - guarded by selection filtering
                    raise RuntimeError(f"Unsupported projection type {job.projection_type}")
            except Exception as exc:  # pragma: no cover - exercised via tests with fakes
                failed.append(mark_projection_job_failed(job.id, f"Replay failed: {exc}"))
            else:
                completed.append(mark_projection_job_completed(job.id))

    return ReplayProjectionResult(
        selected_entries=len(selection.entries),
        selected_jobs=selected_jobs,
        completed_jobs=len(completed),
        failed_jobs=len(failed),
        jobs=[*completed, *failed],
    )
