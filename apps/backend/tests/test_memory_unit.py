from midas.core.memory import MemoryMemoryStore, PROJECTION_TYPES


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
