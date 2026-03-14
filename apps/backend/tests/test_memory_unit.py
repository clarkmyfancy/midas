from midas.core.memory import MemoryMemoryStore, PROJECTION_TYPES
from midas.core.projections import ExtractedEntity, GraphExtraction, GraphProjector, heuristic_extract_graph


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


def test_memory_store_delete_user_data_removes_only_current_users_records() -> None:
    store = MemoryMemoryStore()
    owner_entry, owner_jobs = store.create_journal_entry(
        user_id="user-1",
        journal_entry="Owner entry",
        goals=["Exercise"],
        thread_id=None,
        steps=None,
        sleep_hours=None,
        hrv_ms=None,
        source="manual",
    )
    other_entry, _ = store.create_journal_entry(
        user_id="user-2",
        journal_entry="Other entry",
        goals=[],
        thread_id=None,
        steps=None,
        sleep_hours=None,
        hrv_ms=None,
        source="manual",
    )
    task = store.create_clarification_task(
        user_id="user-1",
        source_record_id=owner_entry.id,
        entity_type="person",
        raw_name="Josh",
        candidate_canonical_name="joshua",
        prompt="Does Josh refer to Joshua?",
        options=["confirm_merge", "keep_separate", "dismiss"],
        confidence=0.63,
        evidence="Alias normalization inferred a merge.",
    )
    store.resolve_clarification_task(
        user_id="user-1",
        task_id=task.id,
        resolution="confirm_merge",
    )

    deleted = store.delete_user_data("user-1")

    assert deleted.deleted_entry_ids == [owner_entry.id]
    assert {job_id for job_id in deleted.deleted_projection_job_ids} == {job.id for job in owner_jobs}
    assert deleted.deleted_clarification_task_ids == [task.id]
    assert deleted.deleted_alias_resolution_count == 1
    assert store.list_journal_entries("user-1") == []
    assert store.list_projection_jobs("user-1") == []
    assert store.list_clarification_tasks("user-1") == []
    assert store.get_alias_resolution(user_id="user-1", entity_type="person", raw_name="Josh") is None
    assert [entry.id for entry in store.list_journal_entries("user-2")] == [other_entry.id]


def test_memory_store_delete_local_data_removes_all_memory_records_but_not_auth() -> None:
    store = MemoryMemoryStore()
    first_entry, first_jobs = store.create_journal_entry(
        user_id="user-1",
        journal_entry="First entry",
        goals=[],
        thread_id=None,
        steps=None,
        sleep_hours=None,
        hrv_ms=None,
        source="manual",
    )
    second_entry, second_jobs = store.create_journal_entry(
        user_id="user-2",
        journal_entry="Second entry",
        goals=[],
        thread_id=None,
        steps=None,
        sleep_hours=None,
        hrv_ms=None,
        source="manual",
    )
    first_task = store.create_clarification_task(
        user_id="user-1",
        source_record_id=first_entry.id,
        entity_type="person",
        raw_name="Josh",
        candidate_canonical_name="joshua",
        prompt="Does Josh refer to Joshua?",
        options=["confirm_merge", "keep_separate", "dismiss"],
        confidence=0.63,
        evidence="Alias normalization inferred a merge.",
    )
    store.resolve_clarification_task(
        user_id="user-1",
        task_id=first_task.id,
        resolution="confirm_merge",
    )

    deleted = store.delete_local_data()

    assert deleted.deleted_entry_ids == [second_entry.id, first_entry.id]
    assert {job_id for job_id in deleted.deleted_projection_job_ids} == {
        job.id for job in [*first_jobs, *second_jobs]
    }
    assert deleted.deleted_clarification_task_ids == [first_task.id]
    assert deleted.deleted_alias_resolution_count == 1
    assert store.list_journal_entries("user-1") == []
    assert store.list_journal_entries("user-2") == []
    assert store.list_projection_jobs("user-1") == []
    assert store.list_projection_jobs("user-2") == []


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
    assert len(person_entities) == 3
    assert {entity.canonical_name for entity in person_entities} >= {"josh", "joshua", "self"}
    josh_entity = next(entity for entity in person_entities if entity.canonical_name == "josh")
    assert set(josh_entity.aliases) >= {"Josh"}
    assert josh_entity.needs_clarification is True
    assert josh_entity.candidate_canonical_name == "joshua"
    assert any(relationship.relationship_type in {"affected", "contributed_to", "led_up_to"} for relationship in extraction.relationships)


def test_heuristic_graph_extractor_normalizes_first_person_to_self() -> None:
    entry, _ = MemoryMemoryStore().create_journal_entry(
        user_id="user-1",
        journal_entry="I felt anxious after work and told myself to slow down.",
        goals=[],
        thread_id=None,
        steps=None,
        sleep_hours=None,
        hrv_ms=None,
        source="manual",
    )

    extraction = heuristic_extract_graph(entry)

    self_entity = next(entity for entity in extraction.entities if entity.entity_type == "person")
    assert self_entity.canonical_name == "self"
    assert "I" in self_entity.aliases
    assert any(
        relationship.source_canonical_name == "self" and relationship.target_canonical_name == "anxious"
        for relationship in extraction.relationships
    )


def test_clarification_resolution_guides_future_alias_handling() -> None:
    store = MemoryMemoryStore()
    task = store.create_clarification_task(
        user_id="user-1",
        source_record_id="entry-1",
        entity_type="person",
        raw_name="Josh",
        candidate_canonical_name="joshua",
        prompt="Does Josh refer to Joshua?",
        options=["confirm_merge", "keep_separate", "dismiss"],
        confidence=0.63,
        evidence="Alias normalization inferred a merge.",
    )

    resolved = store.resolve_clarification_task(
        user_id="user-1",
        task_id=task.id,
        resolution="keep_separate",
    )
    alias_resolution = store.get_alias_resolution(
        user_id="user-1",
        entity_type="person",
        raw_name="Josh",
    )

    assert resolved.status == "resolved"
    assert resolved.resolution == "keep_separate"
    assert resolved.resolved_canonical_name == "josh"
    assert alias_resolution is not None
    assert alias_resolution.resolution == "keep_separate"
    assert alias_resolution.resolved_canonical_name == "josh"


def test_prepare_extraction_flags_typo_like_person_match_for_clarification(monkeypatch) -> None:
    entry, _ = MemoryMemoryStore().create_journal_entry(
        user_id="user-1",
        journal_entry="Torian and I talked after work.",
        goals=[],
        thread_id=None,
        steps=None,
        sleep_hours=None,
        hrv_ms=None,
        source="manual",
    )
    projector = GraphProjector(base_url="http://127.0.0.1:7474")
    extraction = GraphExtraction(
        summary="person=tofian",
        entities=[
            ExtractedEntity(
                entity_type="person",
                name="Tofian",
                canonical_name="tofian",
                confidence=0.91,
                evidence="Named person mention 'Tofian'.",
                aliases=["Tofian"],
            )
        ],
        relationships=[],
    )

    monkeypatch.setattr(
        projector,
        "list_entities",
        lambda user_id, entity_type: [
            {
                "canonical_name": "torian",
                "display_name": "Torian",
                "aliases": ["Torian"],
                "max_confidence": 0.88,
                "observation_count": 3,
            }
        ],
    )

    prepared = projector.prepare_extraction(entry, extraction)

    assert prepared.entities[0].canonical_name == "tofian"
    assert prepared.entities[0].needs_clarification is True
    assert prepared.entities[0].candidate_canonical_name == "torian"
    assert prepared.entities[0].confidence < 0.91


def test_prepare_extraction_merges_current_user_aliases_without_clarification() -> None:
    entry, _ = MemoryMemoryStore().create_journal_entry(
        user_id="user-1",
        journal_entry="I told myself to reset after work.",
        goals=[],
        thread_id=None,
        steps=None,
        sleep_hours=None,
        hrv_ms=None,
        source="manual",
    )
    projector = GraphProjector(base_url="http://127.0.0.1:7474")
    extraction = GraphExtraction(
        summary="person=self",
        entities=[
            ExtractedEntity(
                entity_type="person",
                name="I",
                canonical_name="i",
                confidence=0.87,
                evidence="First-person reference.",
                aliases=["I"],
            ),
            ExtractedEntity(
                entity_type="person",
                name="self",
                canonical_name="self",
                confidence=0.82,
                evidence="Self-reference.",
                aliases=["self"],
            ),
        ],
        relationships=[],
    )

    prepared = projector.prepare_extraction(entry, extraction)

    assert len(prepared.entities) == 1
    assert prepared.entities[0].canonical_name == "self"
    assert prepared.entities[0].name == "Self"
    assert prepared.entities[0].needs_clarification is False
    assert set(prepared.entities[0].aliases) >= {"I", "self"}
