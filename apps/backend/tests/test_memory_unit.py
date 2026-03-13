from midas.core.memory import MemoryMemoryStore, PROJECTION_TYPES
from midas.core.projections import heuristic_extract_graph


def test_memory_store_creates_entry_and_projection_jobs() -> None:
    store = MemoryMemoryStore()

    entry, jobs = store.create_journal_entry(
        user_id="user-1",
        journal_entry="I stayed up late working and skipped the gym.",
        goals=["Protect recovery"],
        thread_id="thread-1",
        steps=3200,
        sleep_hours=5.4,
        hrv_ms=29.0,
        source="manual",
    )

    assert entry.user_id == "user-1"
    assert entry.thread_id == "thread-1"
    assert entry.goals == ["Protect recovery"]
    assert {job.projection_type for job in jobs} == set(PROJECTION_TYPES)
    assert all(job.source_record_id == entry.id for job in jobs)
    assert all(job.status == "pending" for job in jobs)


def test_memory_store_filters_jobs_by_user_and_source_record() -> None:
    store = MemoryMemoryStore()
    first_entry, _ = store.create_journal_entry(
        user_id="user-1",
        journal_entry="First",
        goals=[],
        thread_id=None,
        steps=None,
        sleep_hours=None,
        hrv_ms=None,
        source="manual",
    )
    second_entry, _ = store.create_journal_entry(
        user_id="user-1",
        journal_entry="Second",
        goals=[],
        thread_id=None,
        steps=None,
        sleep_hours=None,
        hrv_ms=None,
        source="manual",
    )
    store.create_journal_entry(
        user_id="user-2",
        journal_entry="Third",
        goals=[],
        thread_id=None,
        steps=None,
        sleep_hours=None,
        hrv_ms=None,
        source="manual",
    )

    first_jobs = store.list_projection_jobs("user-1", source_record_id=first_entry.id)
    second_jobs = store.list_projection_jobs("user-1", source_record_id=second_entry.id)
    foreign_jobs = store.list_projection_jobs("user-2")

    assert len(first_jobs) == len(PROJECTION_TYPES)
    assert len(second_jobs) == len(PROJECTION_TYPES)
    assert len(foreign_jobs) == len(PROJECTION_TYPES)
    assert all(job.source_record_id == first_entry.id for job in first_jobs)
    assert all(job.source_record_id == second_entry.id for job in second_jobs)


def test_memory_store_delete_removes_entry_and_projection_jobs() -> None:
    store = MemoryMemoryStore()
    entry, jobs = store.create_journal_entry(
        user_id="user-1",
        journal_entry="Delete me",
        goals=["Exercise"],
        thread_id=None,
        steps=None,
        sleep_hours=None,
        hrv_ms=None,
        source="manual",
    )

    deleted = store.delete_journal_entry("user-1", entry.id)

    assert deleted is not None
    deleted_entry, deleted_jobs = deleted
    assert deleted_entry.id == entry.id
    assert {job.id for job in deleted_jobs} == {job.id for job in jobs}
    assert store.get_journal_entry("user-1", entry.id) is None
    assert store.list_projection_jobs("user-1", source_record_id=entry.id) == []


def test_heuristic_graph_extractor_merges_person_aliases_and_builds_relationships() -> None:
    entry, _ = MemoryMemoryStore().create_journal_entry(
        user_id="user-1",
        journal_entry=(
            "Josh said the meeting at work ran late. After talking with Joshua, "
            "I felt anxious and skipped my workout because sleep was bad."
        ),
        goals=["Protect recovery", "Exercise"],
        thread_id=None,
        steps=3200,
        sleep_hours=5.1,
        hrv_ms=31.0,
        source="manual",
    )

    extraction = heuristic_extract_graph(entry)

    person_entities = [entity for entity in extraction.entities if entity.entity_type == "person"]
    assert len(person_entities) == 1
    assert person_entities[0].canonical_name == "joshua"
    assert set(person_entities[0].aliases) >= {"Josh", "Joshua"}
    assert person_entities[0].needs_clarification is True
    assert any(relationship.relationship_type in {"affected", "contributed_to", "led_up_to"} for relationship in extraction.relationships)
