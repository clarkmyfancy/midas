from __future__ import annotations

from datetime import UTC, datetime

import pytest

from midas.core.memory import (
    JournalEntryRecord,
    NEO4J_KNOWLEDGE_GRAPH_PROJECTION,
    ProjectionJobRecord,
    WEAVIATE_RAW_JOURNAL_PROJECTION,
    WEAVIATE_SEMANTIC_SUMMARY_PROJECTION,
)
from midas.core.replay import replay_projection_scope, resolve_replay_projection_types


def make_entry(*, entry_id: str, user_id: str) -> JournalEntryRecord:
    return JournalEntryRecord(
        id=entry_id,
        user_id=user_id,
        journal_entry="Replay this entry.",
        goals=["Ship Midas"],
        thread_id="replay-thread",
        steps=None,
        sleep_hours=None,
        hrv_ms=None,
        source="manual",
        created_at=datetime.now(UTC),
    )


def make_job(*, job_id: str, entry_id: str, user_id: str, projection_type: str) -> ProjectionJobRecord:
    return ProjectionJobRecord(
        id=job_id,
        user_id=user_id,
        source_record_id=entry_id,
        source_record_type="journal_entry",
        projection_type=projection_type,
        status="completed",
        attempts=1,
        created_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        last_error=None,
    )


def test_resolve_replay_projection_types_supports_all_targets() -> None:
    assert resolve_replay_projection_types("all") == (
        WEAVIATE_RAW_JOURNAL_PROJECTION,
        WEAVIATE_SEMANTIC_SUMMARY_PROJECTION,
        NEO4J_KNOWLEDGE_GRAPH_PROJECTION,
    )
    assert resolve_replay_projection_types("weaviate") == (
        WEAVIATE_RAW_JOURNAL_PROJECTION,
        WEAVIATE_SEMANTIC_SUMMARY_PROJECTION,
    )
    assert resolve_replay_projection_types("neo4j") == (NEO4J_KNOWLEDGE_GRAPH_PROJECTION,)


def test_resolve_replay_projection_types_rejects_unknown_target() -> None:
    with pytest.raises(ValueError, match="Unsupported replay target"):
        resolve_replay_projection_types("unknown")


def test_replay_projection_scope_targets_only_requested_store(monkeypatch) -> None:
    entry = make_entry(entry_id="entry-1", user_id="user-1")
    jobs = [
        make_job(
            job_id="weaviate-raw",
            entry_id=entry.id,
            user_id=entry.user_id,
            projection_type=WEAVIATE_RAW_JOURNAL_PROJECTION,
        ),
        make_job(
            job_id="weaviate-semantic",
            entry_id=entry.id,
            user_id=entry.user_id,
            projection_type=WEAVIATE_SEMANTIC_SUMMARY_PROJECTION,
        ),
        make_job(
            job_id="neo4j-graph",
            entry_id=entry.id,
            user_id=entry.user_id,
            projection_type=NEO4J_KNOWLEDGE_GRAPH_PROJECTION,
        ),
    ]
    events: list[tuple[str, str]] = []

    class FakeWeaviateProjector:
        def delete_objects(self, object_ids: list[str]):
            events.append(("weaviate-delete", ",".join(object_ids)))

        def project(self, job, _entry) -> None:
            events.append(("weaviate-project", job.id))

    class FakeGraphProjector:
        def delete_observation(self, source_record_id: str, user_id: str):
            events.append(("neo4j-delete", f"{user_id}:{source_record_id}"))

        def project(self, job, _entry) -> None:
            events.append(("neo4j-project", job.id))

    monkeypatch.setattr("midas.core.replay.load_replay_entries", lambda **_kwargs: [entry])
    monkeypatch.setattr("midas.core.replay.list_projection_jobs_for_user", lambda _user_id, source_record_id=None: jobs)
    monkeypatch.setattr("midas.core.replay.WeaviateProjector", FakeWeaviateProjector)
    monkeypatch.setattr("midas.core.replay.GraphProjector", FakeGraphProjector)
    monkeypatch.setattr("midas.core.replay.mark_projection_job_completed", lambda job_id: next(job for job in jobs if job.id == job_id))
    monkeypatch.setattr("midas.core.replay.mark_projection_job_failed", lambda job_id, message: next(job for job in jobs if job.id == job_id))

    result = replay_projection_scope(target="weaviate", entry_id=entry.id)

    assert result.selected_entries == 1
    assert result.selected_jobs == 2
    assert result.completed_jobs == 2
    assert result.failed_jobs == 0
    assert ("weaviate-delete", "weaviate-raw,weaviate-semantic") in events
    assert ("weaviate-project", "weaviate-raw") in events
    assert ("weaviate-project", "weaviate-semantic") in events
    assert not any(event[0].startswith("neo4j") for event in events)


def test_replay_projection_scope_supports_dry_run(monkeypatch) -> None:
    entry = make_entry(entry_id="entry-1", user_id="user-1")
    jobs = [
        make_job(
            job_id="weaviate-raw",
            entry_id=entry.id,
            user_id=entry.user_id,
            projection_type=WEAVIATE_RAW_JOURNAL_PROJECTION,
        ),
        make_job(
            job_id="neo4j-graph",
            entry_id=entry.id,
            user_id=entry.user_id,
            projection_type=NEO4J_KNOWLEDGE_GRAPH_PROJECTION,
        ),
    ]

    monkeypatch.setattr("midas.core.replay.load_replay_entries", lambda **_kwargs: [entry])
    monkeypatch.setattr("midas.core.replay.list_projection_jobs_for_user", lambda _user_id, source_record_id=None: jobs)

    class UnexpectedProjector:
        def __init__(self, *args, **kwargs) -> None:
            raise AssertionError("Projectors should not be created during dry-run")

    monkeypatch.setattr("midas.core.replay.WeaviateProjector", UnexpectedProjector)
    monkeypatch.setattr("midas.core.replay.GraphProjector", UnexpectedProjector)

    result = replay_projection_scope(target="all", entry_id=entry.id, dry_run=True)

    assert result.selected_entries == 1
    assert result.selected_jobs == 2
    assert result.completed_jobs == 0
    assert result.failed_jobs == 0
    assert result.jobs == []
