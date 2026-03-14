from midas.core.memory import (
    MemoryMemoryStore,
    PROJECTION_TYPES,
    WEAVIATE_RAW_JOURNAL_PROJECTION,
    WEAVIATE_SEMANTIC_SUMMARY_PROJECTION,
)
from midas.core.projections import (
    ExtractedEntity,
    ExtractedRelationship,
    GraphExtraction,
    GraphProjector,
    WEAVIATE_CLASS_PROPERTIES,
    build_weaviate_projection_payload,
    heuristic_extract_graph,
    normalize_extraction,
)


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


def test_weaviate_projection_payload_distinguishes_raw_and_semantic_content() -> None:
    store = MemoryMemoryStore()
    entry, jobs = store.create_journal_entry(
        user_id="user-1",
        journal_entry="I felt pretty pumped becasue the Midas setup is working and communicating clearly now.",
        goals=["Ship Midas"],
        thread_id="dashboard-chat",
        steps=None,
        sleep_hours=None,
        hrv_ms=None,
        source="reflection_api",
    )
    raw_job = next(job for job in jobs if job.projection_type == WEAVIATE_RAW_JOURNAL_PROJECTION)
    semantic_job = next(job for job in jobs if job.projection_type == WEAVIATE_SEMANTIC_SUMMARY_PROJECTION)

    raw_content, raw_embedding_text, raw_properties = build_weaviate_projection_payload(raw_job, entry)
    semantic_content, semantic_embedding_text, semantic_properties = build_weaviate_projection_payload(semantic_job, entry)

    assert raw_content == entry.journal_entry
    assert raw_properties["content_kind"] == "raw_journal_entry"
    assert raw_properties["goals"] == ["Ship Midas"]
    assert raw_properties["projection_version"] == "v2"
    assert "because" in raw_embedding_text
    assert semantic_properties["content_kind"] == "semantic_summary"
    assert semantic_content != entry.journal_entry
    assert "Episode summary:" not in semantic_content
    assert "Midas" in semantic_content
    assert "because" in semantic_embedding_text
    assert semantic_properties["goals"] == ["Ship Midas"]


def test_weaviate_schema_uses_date_and_filterable_metadata_defaults() -> None:
    properties_by_name = {item["name"]: item for item in WEAVIATE_CLASS_PROPERTIES}

    assert properties_by_name["created_at"]["dataType"] == ["date"]
    assert properties_by_name["created_at"]["indexFilterable"] is True
    assert properties_by_name["user_id"]["indexSearchable"] is False
    assert properties_by_name["source_record_id"]["indexSearchable"] is False
    assert properties_by_name["projection_type"]["indexSearchable"] is False
    assert properties_by_name["organizations"]["indexSearchable"] is False
    assert properties_by_name["content"]["indexSearchable"] is True
    assert properties_by_name["normalized_content"]["indexSearchable"] is True


def test_weaviate_projection_payload_filters_bad_person_and_project_candidates() -> None:
    store = MemoryMemoryStore()

    ambiguous_entry, ambiguous_jobs = store.create_journal_entry(
        user_id="user-1",
        journal_entry="tofian is fun to hang with sometimes, and sometimes we have issues communicting",
        goals=[],
        thread_id="dashboard-chat",
        steps=None,
        sleep_hours=None,
        hrv_ms=None,
        source="reflection_api",
    )
    ambiguous_job = next(job for job in ambiguous_jobs if job.projection_type == WEAVIATE_SEMANTIC_SUMMARY_PROJECTION)
    ambiguous_content, _embedding_text, ambiguous_properties = build_weaviate_projection_payload(ambiguous_job, ambiguous_entry)

    assert ambiguous_properties["people"] == []
    assert "hang_with" not in ambiguous_properties["canonical_entities"]
    assert ambiguous_content.startswith("Journal note about")

    torian_entry, torian_jobs = store.create_journal_entry(
        user_id="user-1",
        journal_entry="i'm feeling pretty great about how i got all of this working. it's funny though, when i was working with torian it took for fucking ever",
        goals=[],
        thread_id="dashboard-chat",
        steps=None,
        sleep_hours=None,
        hrv_ms=None,
        source="reflection_api",
    )
    torian_job = next(job for job in torian_jobs if job.projection_type == WEAVIATE_SEMANTIC_SUMMARY_PROJECTION)
    torian_content, _embedding_text, torian_properties = build_weaviate_projection_payload(torian_job, torian_entry)

    assert torian_properties["people"] == ["Torian"]
    assert "torian_it" not in torian_properties["canonical_entities"]
    assert "Torian It" not in torian_content

    project_entry, project_jobs = store.create_journal_entry(
        user_id="user-1",
        journal_entry="i should mention that 'this project' refers to Midas. all of the recent entries i've done refer to that one and when i say the 'last project' i'm referring to thrivesight",
        goals=[],
        thread_id="dashboard-chat",
        steps=None,
        sleep_hours=None,
        hrv_ms=None,
        source="reflection_api",
    )
    project_job = next(job for job in project_jobs if job.projection_type == WEAVIATE_SEMANTIC_SUMMARY_PROJECTION)
    project_content, _embedding_text, project_properties = build_weaviate_projection_payload(project_job, project_entry)

    assert project_properties["people"] == []
    assert set(project_properties["projects"]) >= {"midas", "thrivesight"}
    assert set(project_properties["canonical_entities"]) >= {"midas", "thrivesight"}
    assert "That One" not in project_content

    local_entry, local_jobs = store.create_journal_entry(
        user_id="user-1",
        journal_entry="i'm feeling pretty pumped becasue this is set up and working on local now!",
        goals=[],
        thread_id="dashboard-chat",
        steps=None,
        sleep_hours=None,
        hrv_ms=None,
        source="reflection_api",
    )
    local_job = next(job for job in local_jobs if job.projection_type == WEAVIATE_SEMANTIC_SUMMARY_PROJECTION)
    local_content, _embedding_text, local_properties = build_weaviate_projection_payload(local_job, local_entry)

    assert local_properties["projects"] == []
    assert "local_now" not in local_properties["canonical_entities"]
    assert "Focus on local now" not in local_content


def test_weaviate_projection_payload_uses_shared_model_extraction_for_organizations(monkeypatch) -> None:
    store = MemoryMemoryStore()
    entry, jobs = store.create_journal_entry(
        user_id="user-1",
        journal_entry="OpenAI reached out about a possible partnership.",
        goals=[],
        thread_id="dashboard-chat",
        steps=None,
        sleep_hours=None,
        hrv_ms=None,
        source="reflection_api",
    )
    semantic_job = next(job for job in jobs if job.projection_type == WEAVIATE_SEMANTIC_SUMMARY_PROJECTION)

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        "midas.core.projections.extract_graph_with_model",
        lambda current_entry: GraphExtraction(
            summary="Company outreach from OpenAI.",
            entities=[
                ExtractedEntity(
                    entity_type="company",
                    name="OpenAI",
                    canonical_name="openai",
                    confidence=0.93,
                    evidence="The journal explicitly mentions OpenAI.",
                    aliases=["OpenAI"],
                )
            ],
            relationships=[],
        ),
    )

    semantic_content, semantic_embedding_text, semantic_properties = build_weaviate_projection_payload(semantic_job, entry)

    assert semantic_properties["organizations"] == ["OpenAI"]
    assert semantic_properties["people"] == []
    assert "openai" in semantic_properties["canonical_entities"]
    assert "OpenAI" in semantic_content
    assert "OpenAI" in semantic_embedding_text


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


def test_normalize_extraction_corrects_project_precedes_direction_from_alias_language() -> None:
    entry, _ = MemoryMemoryStore().create_journal_entry(
        user_id="user-1",
        journal_entry=(
            "i should mention that 'this project' refers to Midas. all of the recent entries i've done refer to that one "
            "and when i say the 'last project' i'm referring to thrivesight"
        ),
        goals=[],
        thread_id="dashboard-chat",
        steps=None,
        sleep_hours=None,
        hrv_ms=None,
        source="reflection_api",
    )
    extraction = GraphExtraction(
        summary="midas and thrivesight relationship",
        entities=[
            ExtractedEntity(
                entity_type="project",
                name="Midas",
                canonical_name="midas",
                confidence=0.95,
                evidence="Current project alias.",
                aliases=["Midas"],
            ),
            ExtractedEntity(
                entity_type="project",
                name="thrivesight",
                canonical_name="thrivesight",
                confidence=0.95,
                evidence="Last project alias.",
                aliases=["thrivesight"],
            ),
        ],
        relationships=[
            ExtractedRelationship(
                source_canonical_name="midas",
                target_canonical_name="thrivesight",
                relationship_type="precedes",
                confidence=0.75,
                evidence="Model guessed the direction.",
            )
        ],
    )

    normalized = normalize_extraction(entry, extraction)
    precedes_relationships = [
        relationship
        for relationship in normalized.relationships
        if relationship.relationship_type == "precedes"
    ]

    assert len(precedes_relationships) == 1
    assert precedes_relationships[0].source_canonical_name == "thrivesight"
    assert precedes_relationships[0].target_canonical_name == "midas"
