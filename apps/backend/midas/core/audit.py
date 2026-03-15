from __future__ import annotations

from dataclasses import dataclass

from midas.core.memory import (
    NEO4J_PROJECTION_TYPES,
    WEAVIATE_PROJECTION_TYPES,
    list_journal_entries_for_user,
    list_projection_jobs_for_user,
)
from midas.core.projections import GraphProjector, WeaviateProjector


@dataclass(frozen=True)
class ProjectionStoreAudit:
    store: str
    status: str
    total_jobs: int
    completed_jobs: int
    pending_jobs: int
    failed_jobs: int
    present_artifacts: int
    missing_completed_artifacts: int
    affected_entry_ids: list[str]
    missing_job_ids: list[str]
    failed_job_ids: list[str]


@dataclass(frozen=True)
class MemoryProjectionAudit:
    total_entries: int
    total_projection_jobs: int
    completed_jobs: int
    pending_jobs: int
    failed_jobs: int
    drifted_entry_ids: list[str]
    stores: list[ProjectionStoreAudit]


def _build_store_audit(*, store: str, jobs, is_present) -> ProjectionStoreAudit:
    completed = [job for job in jobs if job.status == "completed"]
    pending = [job for job in jobs if job.status == "pending"]
    failed = [job for job in jobs if job.status == "failed"]

    present_artifacts = 0
    missing_completed_job_ids: list[str] = []
    affected_entry_ids = {job.source_record_id for job in failed}

    for job in completed:
        if is_present(job):
            present_artifacts += 1
            continue
        missing_completed_job_ids.append(job.id)
        affected_entry_ids.add(job.source_record_id)

    status = "ok"
    if failed or missing_completed_job_ids:
        status = "attention"

    return ProjectionStoreAudit(
        store=store,
        status=status,
        total_jobs=len(jobs),
        completed_jobs=len(completed),
        pending_jobs=len(pending),
        failed_jobs=len(failed),
        present_artifacts=present_artifacts,
        missing_completed_artifacts=len(missing_completed_job_ids),
        affected_entry_ids=sorted(affected_entry_ids),
        missing_job_ids=sorted(missing_completed_job_ids),
        failed_job_ids=sorted(job.id for job in failed),
    )


def build_memory_projection_audit(user_id: str) -> MemoryProjectionAudit:
    entries = list_journal_entries_for_user(user_id)
    jobs = list_projection_jobs_for_user(user_id)
    entry_ids = {entry.id for entry in entries}

    weaviate = WeaviateProjector()
    graph = GraphProjector()
    graph_cache: dict[str, bool] = {}

    weaviate_jobs = [job for job in jobs if job.projection_type in WEAVIATE_PROJECTION_TYPES]
    graph_jobs = [job for job in jobs if job.projection_type in NEO4J_PROJECTION_TYPES]

    def weaviate_present(job) -> bool:
        try:
            return weaviate.fetch_object(job.id) is not None
        except RuntimeError:
            return False

    def graph_present(job) -> bool:
        cached = graph_cache.get(job.source_record_id)
        if cached is not None:
            return cached
        if job.source_record_id not in entry_ids:
            graph_cache[job.source_record_id] = False
            return False
        try:
            payload = graph.fetch_observation(job.source_record_id, user_id)
        except RuntimeError:
            graph_cache[job.source_record_id] = False
            return False
        observation = payload.get("observation")
        resolved = isinstance(observation, dict) and bool(observation)
        graph_cache[job.source_record_id] = resolved
        return resolved

    store_audits = [
        _build_store_audit(store="weaviate", jobs=weaviate_jobs, is_present=weaviate_present),
        _build_store_audit(store="neo4j", jobs=graph_jobs, is_present=graph_present),
    ]

    return MemoryProjectionAudit(
        total_entries=len(entries),
        total_projection_jobs=len(jobs),
        completed_jobs=sum(1 for job in jobs if job.status == "completed"),
        pending_jobs=sum(1 for job in jobs if job.status == "pending"),
        failed_jobs=sum(1 for job in jobs if job.status == "failed"),
        drifted_entry_ids=sorted({entry_id for audit in store_audits for entry_id in audit.affected_entry_ids}),
        stores=store_audits,
    )
