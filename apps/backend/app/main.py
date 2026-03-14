import os
from pathlib import Path
from collections.abc import AsyncIterator
from typing import Annotated

from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi import HTTPException, status
from fastapi.responses import StreamingResponse


backend_env_dir = Path(__file__).resolve().parents[1]
load_dotenv(backend_env_dir / ".env")
if os.getenv("MIDAS_LOAD_DOTENV_LOCAL", "1") != "0":
    load_dotenv(backend_env_dir / ".env.local", override=True)

from app.agents.graph import astream_reflection_workflow
from app.schemas.auth import (
    AuthLoginRequest,
    AuthRegisterRequest,
    AuthTokenResponse,
    AuthUserResponse,
)
from app.schemas.capabilities import CapabilityMapResponse
from app.schemas.journal import (
    ClarificationResolveRequest,
    ClarificationTaskListResponse,
    ClarificationTaskResponse,
    DerivedStoreCleanupResponse,
    GraphNodeResponse,
    GraphObservationResponse,
    GraphRelationshipResponse,
    JournalDeleteResponse,
    JournalEntryCreateRequest,
    JournalEntryListResponse,
    JournalEntryResponse,
    JournalIngestResponse,
    LocalDataWipeResponse,
    UserDataDeleteResponse,
    MemorySettingsResponse,
    MemoryDebugResponse,
    ProjectionJobListResponse,
    ProjectionJobResponse,
    ProjectionRunResponse,
    WeaviateArtifactResponse,
)
from app.schemas.review import ReviewFindingResponse, ReviewStatResponse, WeeklyReviewResponse
from app.schemas.reflection import ReflectionRequest
from midas.core.entitlements import (
    AuthUser,
    create_access_token,
    get_current_user,
    init_auth_storage,
    login_user,
    optional_current_user,
    register_user,
    requires_entitlement,
    resolve_capabilities_for_user,
)
from midas.core.loader import load_capabilities
from midas.core.memory import (
    create_journal_entry_for_user,
    delete_local_data,
    delete_journal_entry_for_user,
    delete_user_data_for_user,
    list_clarification_tasks_for_user,
    get_journal_entry_for_user,
    init_memory_storage,
    list_journal_entries_for_user,
    list_projection_jobs_for_user,
    resolve_clarification_task_for_user,
)
from midas.core.projections import (
    GraphProjector,
    VECTOR_CLASS_NAME,
    WeaviateProjector,
    delete_derived_artifacts,
    process_pending_projection_jobs,
)
from midas.core.review import build_weekly_review

app = FastAPI(
    title="Midas API",
    version="0.1.0",
    description="Backend scaffold for the Midas multi-agent reflection system.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

load_capabilities()
init_auth_storage()
init_memory_storage()


def is_development_mode() -> bool:
    environment = os.getenv("MIDAS_ENV") or os.getenv("NODE_ENV") or "development"
    return environment.strip().lower() not in {"prod", "production"}


def serialize_journal_entry(entry) -> JournalEntryResponse:
    return JournalEntryResponse(
        id=entry.id,
        user_id=entry.user_id,
        journal_entry=entry.journal_entry,
        goals=entry.goals,
        thread_id=entry.thread_id,
        steps=entry.steps,
        sleep_hours=entry.sleep_hours,
        hrv_ms=entry.hrv_ms,
        source=entry.source,
        created_at=entry.created_at,
    )


def serialize_projection_job(job) -> ProjectionJobResponse:
    return ProjectionJobResponse(
        id=job.id,
        user_id=job.user_id,
        source_record_id=job.source_record_id,
        source_record_type=job.source_record_type,
        projection_type=job.projection_type,
        status=job.status,
        attempts=job.attempts,
        created_at=job.created_at,
        completed_at=job.completed_at,
        last_error=job.last_error,
    )


def serialize_clarification_task(task) -> ClarificationTaskResponse:
    return ClarificationTaskResponse(
        id=task.id,
        user_id=task.user_id,
        source_record_id=task.source_record_id,
        entity_type=task.entity_type,
        raw_name=task.raw_name,
        candidate_canonical_name=task.candidate_canonical_name,
        status=task.status,
        prompt=task.prompt,
        options=task.options,
        confidence=task.confidence,
        evidence=task.evidence,
        resolution=task.resolution,
        resolved_canonical_name=task.resolved_canonical_name,
        created_at=task.created_at,
        resolved_at=task.resolved_at,
    )


def build_memory_links() -> dict[str, str]:
    weaviate = WeaviateProjector()
    graph = GraphProjector()
    return {
        "neo4j_browser": graph.browser_url(),
        "weaviate_schema": f"{weaviate.base_url}/v1/schema",
        "weaviate_objects": f"{weaviate.base_url}/v1/objects",
    }


def get_memory_settings() -> MemorySettingsResponse:
    return MemorySettingsResponse(
        auto_project_enabled=os.getenv("MIDAS_AUTO_PROJECT", "0") == "1",
    )


def serialize_graph_node(node: dict[str, object]) -> GraphNodeResponse:
    return GraphNodeResponse(
        node_id=str(node.get("id", "")),
        labels=[str(label) for label in node.get("labels", [])],
        properties=dict(node.get("properties", {})),
    )


def serialize_graph_relationship(relationship: dict[str, object]) -> GraphRelationshipResponse:
    return GraphRelationshipResponse(
        relationship_id=str(relationship.get("id", "")),
        type=str(relationship.get("type", "")),
        start_node_id=str(relationship.get("startNode", "")),
        end_node_id=str(relationship.get("endNode", "")),
        properties=dict(relationship.get("properties", {})),
    )


def serialize_review_finding(finding) -> ReviewFindingResponse:
    return ReviewFindingResponse(
        title=finding.title,
        detail=finding.detail,
        evidence=finding.evidence,
    )


def serialize_review_stat(stat) -> ReviewStatResponse:
    return ReviewStatResponse(label=stat.label, value=stat.value)


async def stream_reflection_events(payload: ReflectionRequest) -> AsyncIterator[str]:
    async for chunk in astream_reflection_workflow(payload):
        if not isinstance(chunk, tuple) or len(chunk) != 2:
            continue

        mode, payload_chunk = chunk
        if mode != "custom" or not isinstance(payload_chunk, dict):
            continue

        token = payload_chunk.get("token")
        if isinstance(token, str) and token:
            yield f"data: {token}\n\n"


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/memory/settings", response_model=MemorySettingsResponse)
@app.get("/v1/memory/settings", response_model=MemorySettingsResponse)
def memory_settings() -> MemorySettingsResponse:
    return get_memory_settings()


@app.get("/api/v1/review", response_model=WeeklyReviewResponse)
@app.get("/v1/review", response_model=WeeklyReviewResponse)
def get_weekly_review(
    user: Annotated[AuthUser, Depends(get_current_user)],
    window_days: int = 7,
) -> WeeklyReviewResponse:
    result = build_weekly_review(user_id=user.id, window_days=window_days)
    return WeeklyReviewResponse(
        summary=result.summary,
        generated_at=result.generated_at,
        window_days=result.window_days,
        findings=[serialize_review_finding(finding) for finding in result.findings],
        stats=[serialize_review_stat(stat) for stat in result.stats],
        entries=[serialize_journal_entry(entry) for entry in result.entries],
        memory_highlights=[
            WeaviateArtifactResponse(
                projection_job_id=str(artifact.get("projection_job_id", "")),
                object_id=str(artifact.get("object_id", "")),
                class_name=str(artifact.get("class_name", "")),
                content=artifact.get("content"),
                url=artifact.get("url"),
                raw=artifact.get("raw"),
            )
            for artifact in result.memory_highlights
        ],
        graph=GraphObservationResponse(
            observation=None,
            nodes=[serialize_graph_node(node) for node in result.graph_nodes],
            relationships=[serialize_graph_relationship(relationship) for relationship in result.graph_relationships],
            cypher_browser_url=GraphProjector().browser_url(),
        ),
        clarifications=[serialize_clarification_task(task) for task in result.clarifications],
        warnings=result.warnings,
    )


@app.get("/api/v1/clarifications", response_model=ClarificationTaskListResponse)
@app.get("/v1/clarifications", response_model=ClarificationTaskListResponse)
def list_clarifications(
    user: Annotated[AuthUser, Depends(get_current_user)],
    task_status: str | None = None,
) -> ClarificationTaskListResponse:
    tasks = list_clarification_tasks_for_user(user.id, status=task_status)
    return ClarificationTaskListResponse(tasks=[serialize_clarification_task(task) for task in tasks])


@app.post("/api/v1/clarifications/{task_id}/resolve", response_model=ClarificationTaskResponse)
@app.post("/v1/clarifications/{task_id}/resolve", response_model=ClarificationTaskResponse)
def resolve_clarification(
    task_id: str,
    payload: ClarificationResolveRequest,
    user: Annotated[AuthUser, Depends(get_current_user)],
) -> ClarificationTaskResponse:
    try:
        task = resolve_clarification_task_for_user(
            user_id=user.id,
            task_id=task_id,
            resolution=payload.resolution,
            resolved_canonical_name=payload.resolved_canonical_name,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clarification task not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return serialize_clarification_task(task)


@app.post("/api/v1/reflections")
@app.post("/v1/reflections")
async def create_reflection(
    background_tasks: BackgroundTasks,
    payload: ReflectionRequest,
    user: Annotated[AuthUser, Depends(get_current_user)],
) -> StreamingResponse:
    stored_entry, _ = create_journal_entry_for_user(
        user_id=user.id,
        journal_entry=payload.journal_entry,
        goals=payload.goals,
        thread_id=payload.thread_id,
        steps=payload.steps,
        sleep_hours=payload.sleep_hours,
        hrv_ms=payload.hrv_ms,
        source="reflection_api",
    )
    thread_suffix = payload.thread_id or stored_entry.id
    resolved_payload = payload.model_copy(
        update={"thread_id": f"user:{user.id}:{thread_suffix}"}
    )
    if os.getenv("MIDAS_AUTO_PROJECT", "0") == "1":
        process_pending_projection_jobs(limit=10, user_id=user.id)
    return StreamingResponse(
        stream_reflection_events(resolved_payload),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
        background=background_tasks,
    )


@app.post("/api/v1/journal-entries", response_model=JournalIngestResponse)
@app.post("/v1/journal-entries", response_model=JournalIngestResponse)
def create_journal_entry(
    background_tasks: BackgroundTasks,
    payload: JournalEntryCreateRequest,
    user: Annotated[AuthUser, Depends(get_current_user)],
) -> JournalIngestResponse:
    entry, projection_jobs = create_journal_entry_for_user(
        user_id=user.id,
        journal_entry=payload.journal_entry,
        goals=payload.goals,
        thread_id=payload.thread_id,
        steps=payload.steps,
        sleep_hours=payload.sleep_hours,
        hrv_ms=payload.hrv_ms,
        source=payload.source,
    )
    if os.getenv("MIDAS_AUTO_PROJECT", "0") == "1":
        background_tasks.add_task(process_pending_projection_jobs, limit=10, user_id=user.id)
    return JournalIngestResponse(
        entry=serialize_journal_entry(entry),
        projection_jobs=[serialize_projection_job(job) for job in projection_jobs],
    )


@app.get("/api/v1/journal-entries", response_model=JournalEntryListResponse)
@app.get("/v1/journal-entries", response_model=JournalEntryListResponse)
def list_journal_entries(
    user: Annotated[AuthUser, Depends(get_current_user)],
) -> JournalEntryListResponse:
    entries = list_journal_entries_for_user(user.id)
    return JournalEntryListResponse(
        entries=[serialize_journal_entry(entry) for entry in entries],
    )


@app.get("/api/v1/journal-entries/{entry_id}", response_model=JournalEntryResponse)
@app.get("/v1/journal-entries/{entry_id}", response_model=JournalEntryResponse)
def get_journal_entry(
    entry_id: str,
    user: Annotated[AuthUser, Depends(get_current_user)],
) -> JournalEntryResponse:
    entry = get_journal_entry_for_user(user.id, entry_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found")
    return serialize_journal_entry(entry)


@app.delete("/api/v1/journal-entries/{entry_id}", response_model=JournalDeleteResponse)
@app.delete("/v1/journal-entries/{entry_id}", response_model=JournalDeleteResponse)
def delete_journal_entry(
    entry_id: str,
    user: Annotated[AuthUser, Depends(get_current_user)],
) -> JournalDeleteResponse:
    deleted = delete_journal_entry_for_user(user.id, entry_id)
    if deleted is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found")

    entry, jobs = deleted
    cleanup: list[DerivedStoreCleanupResponse] = []

    try:
        weaviate_result, graph_result = delete_derived_artifacts(entry, jobs)
    except Exception as exc:
        cleanup.append(
            DerivedStoreCleanupResponse(
                store="derived_cleanup",
                success=False,
                deleted_count=0,
                error=str(exc),
            )
        )
    else:
        cleanup.append(
            DerivedStoreCleanupResponse(
                store="weaviate",
                success=True,
                deleted_count=len(weaviate_result.deleted_object_ids),
                deleted_ids=weaviate_result.deleted_object_ids,
            )
        )
        cleanup.append(
            DerivedStoreCleanupResponse(
                store="neo4j",
                success=True,
                deleted_count=len(graph_result.deleted_observation_ids) + graph_result.deleted_entities,
                deleted_ids=graph_result.deleted_observation_ids,
                details={
                    "deleted_observation_ids": graph_result.deleted_observation_ids,
                    "deleted_relationships": graph_result.deleted_relationships,
                    "deleted_entities": graph_result.deleted_entities,
                },
            )
        )

    return JournalDeleteResponse(entry_id=entry.id, cleanup=cleanup)


@app.get(
    "/api/v1/journal-entries/{entry_id}/projection-jobs",
    response_model=ProjectionJobListResponse,
)
@app.get(
    "/v1/journal-entries/{entry_id}/projection-jobs",
    response_model=ProjectionJobListResponse,
)
def list_projection_jobs(
    entry_id: str,
    user: Annotated[AuthUser, Depends(get_current_user)],
) -> ProjectionJobListResponse:
    entry = get_journal_entry_for_user(user.id, entry_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found")

    jobs = list_projection_jobs_for_user(user.id, source_record_id=entry_id)
    return ProjectionJobListResponse(
        projection_jobs=[serialize_projection_job(job) for job in jobs],
    )


@app.get("/api/v1/projection-jobs", response_model=ProjectionJobListResponse)
@app.get("/v1/projection-jobs", response_model=ProjectionJobListResponse)
def list_all_projection_jobs(
    user: Annotated[AuthUser, Depends(get_current_user)],
) -> ProjectionJobListResponse:
    jobs = list_projection_jobs_for_user(user.id)
    return ProjectionJobListResponse(
        projection_jobs=[serialize_projection_job(job) for job in jobs],
    )


@app.post("/api/v1/projection-jobs/run", response_model=ProjectionRunResponse)
@app.post("/v1/projection-jobs/run", response_model=ProjectionRunResponse)
def run_projection_jobs(
    user: Annotated[AuthUser, Depends(get_current_user)],
    limit: int = 20,
) -> ProjectionRunResponse:
    result = process_pending_projection_jobs(limit=limit, user_id=user.id)
    return ProjectionRunResponse(
        claimed_jobs=result.claimed_jobs,
        completed_jobs=result.completed_jobs,
        failed_jobs=result.failed_jobs,
        jobs=[serialize_projection_job(job) for job in result.jobs],
    )


@app.get("/api/v1/journal-entries/{entry_id}/debug", response_model=MemoryDebugResponse)
@app.get("/v1/journal-entries/{entry_id}/debug", response_model=MemoryDebugResponse)
def debug_journal_entry(
    entry_id: str,
    user: Annotated[AuthUser, Depends(get_current_user)],
) -> MemoryDebugResponse:
    entry = get_journal_entry_for_user(user.id, entry_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found")

    jobs = list_projection_jobs_for_user(user.id, source_record_id=entry_id)
    weaviate = WeaviateProjector()
    graph = GraphProjector()
    weaviate_artifacts: list[WeaviateArtifactResponse] = []
    for job in jobs:
        if not job.projection_type.startswith("weaviate_"):
            continue
        artifact = weaviate.fetch_object(job.id)
        properties = artifact.get("properties", {}) if artifact else {}
        weaviate_artifacts.append(
            WeaviateArtifactResponse(
                projection_job_id=job.id,
                object_id=job.id,
                class_name=str(artifact.get("class", "")) if artifact else VECTOR_CLASS_NAME,
                content=str(properties.get("content")) if properties.get("content") is not None else None,
                url=weaviate.object_url(job.id),
                raw=artifact,
            )
        )

    try:
        graph_payload = graph.fetch_observation(entry.id, user.id)
    except RuntimeError:
        graph_payload = {"observation": None, "nodes": [], "relationships": []}

    observation = graph_payload.get("observation")
    return MemoryDebugResponse(
        entry=serialize_journal_entry(entry),
        projection_jobs=[serialize_projection_job(job) for job in jobs],
        weaviate_artifacts=weaviate_artifacts,
        graph=GraphObservationResponse(
            observation=serialize_graph_node(observation) if isinstance(observation, dict) else None,
            nodes=[
                serialize_graph_node(node)
                for node in graph_payload.get("nodes", [])
                if isinstance(node, dict)
            ],
            relationships=[
                serialize_graph_relationship(rel)
                for rel in graph_payload.get("relationships", [])
                if isinstance(rel, dict)
            ],
            cypher_browser_url=graph.browser_url(),
        ),
        settings=get_memory_settings(),
        links=build_memory_links(),
    )


@app.post("/api/v1/auth/register", response_model=AuthTokenResponse)
@app.post("/v1/auth/register", response_model=AuthTokenResponse)
def auth_register(payload: AuthRegisterRequest) -> AuthTokenResponse:
    try:
        user = register_user(payload.email, payload.password)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return AuthTokenResponse(
        access_token=create_access_token(user),
        user=AuthUserResponse(id=user.id, email=user.email, is_pro=user.is_pro),
    )


@app.post("/api/v1/auth/login", response_model=AuthTokenResponse)
@app.post("/v1/auth/login", response_model=AuthTokenResponse)
def auth_login(payload: AuthLoginRequest) -> AuthTokenResponse:
    user = login_user(payload.email, payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    return AuthTokenResponse(
        access_token=create_access_token(user),
        user=AuthUserResponse(id=user.id, email=user.email, is_pro=user.is_pro),
    )


@app.get("/api/v1/auth/me", response_model=AuthUserResponse)
@app.get("/v1/auth/me", response_model=AuthUserResponse)
def auth_me(user: Annotated[AuthUser, Depends(get_current_user)]) -> AuthUserResponse:
    return AuthUserResponse(id=user.id, email=user.email, is_pro=user.is_pro)


@app.delete("/api/v1/auth/data", response_model=UserDataDeleteResponse)
@app.delete("/v1/auth/data", response_model=UserDataDeleteResponse)
def auth_delete_user_data(
    user: Annotated[AuthUser, Depends(get_current_user)],
) -> UserDataDeleteResponse:
    deleted = delete_user_data_for_user(user.id)
    cleanup = [
        DerivedStoreCleanupResponse(
            store="postgres",
            success=True,
            deleted_count=(
                len(deleted.deleted_entry_ids)
                + len(deleted.deleted_projection_job_ids)
                + len(deleted.deleted_clarification_task_ids)
                + deleted.deleted_alias_resolution_count
            ),
            deleted_ids=deleted.deleted_entry_ids,
            details={
                "deleted_entry_count": len(deleted.deleted_entry_ids),
                "deleted_projection_job_count": len(deleted.deleted_projection_job_ids),
                "deleted_clarification_task_count": len(deleted.deleted_clarification_task_ids),
                "deleted_alias_resolution_count": deleted.deleted_alias_resolution_count,
            },
        )
    ]

    try:
        weaviate_result = WeaviateProjector().delete_objects(deleted.deleted_projection_job_ids)
    except Exception as exc:
        cleanup.append(
            DerivedStoreCleanupResponse(
                store="weaviate",
                success=False,
                deleted_count=0,
                error=str(exc),
            )
        )
    else:
        cleanup.append(
            DerivedStoreCleanupResponse(
                store="weaviate",
                success=True,
                deleted_count=len(weaviate_result.deleted_object_ids),
                deleted_ids=weaviate_result.deleted_object_ids,
            )
        )

    try:
        graph_result = GraphProjector().delete_user_data(user.id)
    except Exception as exc:
        cleanup.append(
            DerivedStoreCleanupResponse(
                store="neo4j",
                success=False,
                deleted_count=0,
                error=str(exc),
            )
        )
    else:
        cleanup.append(
            DerivedStoreCleanupResponse(
                store="neo4j",
                success=True,
                deleted_count=graph_result.deleted_observations + graph_result.deleted_entities,
                details={
                    "deleted_observation_count": graph_result.deleted_observations,
                    "deleted_entity_count": graph_result.deleted_entities,
                    "deleted_relationship_count": graph_result.deleted_relationships,
                },
            )
        )

    return UserDataDeleteResponse(user_id=user.id, cleanup=cleanup)


@app.delete("/api/v1/dev/local-data", response_model=LocalDataWipeResponse)
@app.delete("/v1/dev/local-data", response_model=LocalDataWipeResponse)
def dev_wipe_local_data(
    _: Annotated[AuthUser, Depends(get_current_user)],
) -> LocalDataWipeResponse:
    if not is_development_mode():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    deleted = delete_local_data()
    cleanup = [
        DerivedStoreCleanupResponse(
            store="postgres",
            success=True,
            deleted_count=(
                len(deleted.deleted_entry_ids)
                + len(deleted.deleted_projection_job_ids)
                + len(deleted.deleted_clarification_task_ids)
                + deleted.deleted_alias_resolution_count
            ),
            deleted_ids=deleted.deleted_entry_ids,
            details={
                "deleted_entry_count": len(deleted.deleted_entry_ids),
                "deleted_projection_job_count": len(deleted.deleted_projection_job_ids),
                "deleted_clarification_task_count": len(deleted.deleted_clarification_task_ids),
                "deleted_alias_resolution_count": deleted.deleted_alias_resolution_count,
            },
        )
    ]

    try:
        weaviate_result = WeaviateProjector().delete_local_data()
    except Exception as exc:
        cleanup.append(
            DerivedStoreCleanupResponse(
                store="weaviate",
                success=False,
                deleted_count=0,
                error=str(exc),
            )
        )
    else:
        cleanup.append(
            DerivedStoreCleanupResponse(
                store="weaviate",
                success=True,
                deleted_count=1 if weaviate_result.deleted_class else 0,
                details={"deleted_class": weaviate_result.deleted_class, "class_name": VECTOR_CLASS_NAME},
            )
        )

    try:
        graph_result = GraphProjector().delete_local_data()
    except Exception as exc:
        cleanup.append(
            DerivedStoreCleanupResponse(
                store="neo4j",
                success=False,
                deleted_count=0,
                error=str(exc),
            )
        )
    else:
        cleanup.append(
            DerivedStoreCleanupResponse(
                store="neo4j",
                success=True,
                deleted_count=graph_result.deleted_observations + graph_result.deleted_entities,
                details={
                    "deleted_observation_count": graph_result.deleted_observations,
                    "deleted_entity_count": graph_result.deleted_entities,
                    "deleted_relationship_count": graph_result.deleted_relationships,
                },
            )
        )

    return LocalDataWipeResponse(cleanup=cleanup)


@app.get("/v1/capabilities", response_model=CapabilityMapResponse)
@app.get("/api/v1/capabilities", response_model=CapabilityMapResponse)
def capability_map(
    user: Annotated[AuthUser | None, Depends(optional_current_user)] = None,
) -> CapabilityMapResponse:
    return CapabilityMapResponse(capabilities=resolve_capabilities_for_user(user))


@app.get("/api/v1/pro/analytics")
def pro_analytics_status(
    _: Annotated[None, Depends(requires_entitlement("pro_analytics"))],
) -> dict[str, str]:
    return {"status": "enabled", "feature": "pro_analytics"}
