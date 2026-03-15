from datetime import datetime

from pydantic import BaseModel, Field


class JournalEntryCreateRequest(BaseModel):
    journal_entry: str = Field(..., min_length=1, description="Journal text to ingest.")
    goals: list[str] = Field(default_factory=list, description="Current goals or priorities.")
    thread_id: str | None = Field(
        default=None,
        description="Optional stable thread identifier to associate with the entry.",
    )
    steps: int | None = Field(default=None, ge=0, description="Daily step count for this entry.")
    sleep_hours: float | None = Field(
        default=None,
        ge=0,
        description="Sleep duration in hours for this entry.",
    )
    hrv_ms: float | None = Field(
        default=None,
        ge=0,
        description="Average heart rate variability in milliseconds for this entry.",
    )
    source: str = Field(
        default="manual",
        min_length=1,
        description="Source label for the canonical journal record.",
    )


class JournalEntryResponse(BaseModel):
    id: str
    user_id: str
    journal_entry: str
    goals: list[str]
    thread_id: str | None
    steps: int | None
    sleep_hours: float | None
    hrv_ms: float | None
    source: str
    created_at: datetime


class ProjectionJobResponse(BaseModel):
    id: str
    user_id: str
    source_record_id: str
    source_record_type: str
    projection_type: str
    status: str
    attempts: int
    created_at: datetime
    completed_at: datetime | None
    last_error: str | None


class JournalIngestResponse(BaseModel):
    entry: JournalEntryResponse
    projection_jobs: list[ProjectionJobResponse]


class JournalEntryListResponse(BaseModel):
    entries: list[JournalEntryResponse]


class ProjectionJobListResponse(BaseModel):
    projection_jobs: list[ProjectionJobResponse]


class ProjectionRunResponse(BaseModel):
    claimed_jobs: int
    completed_jobs: int
    failed_jobs: int
    jobs: list[ProjectionJobResponse]


class MemorySettingsResponse(BaseModel):
    auto_project_enabled: bool
    auto_project_weaviate_enabled: bool
    auto_project_neo4j_enabled: bool


class ClarificationTaskResponse(BaseModel):
    id: str
    user_id: str
    source_record_id: str
    entity_type: str
    raw_name: str
    candidate_canonical_name: str
    status: str
    prompt: str
    options: list[str]
    confidence: float
    evidence: str
    resolution: str | None = None
    resolved_canonical_name: str | None = None
    refresh_status: str | None = None
    refresh_message: str | None = None
    created_at: datetime
    resolved_at: datetime | None = None


class ClarificationTaskListResponse(BaseModel):
    tasks: list[ClarificationTaskResponse]


class ClarificationResolveRequest(BaseModel):
    resolution: str = Field(..., min_length=1)
    resolved_canonical_name: str | None = None


class WeaviateArtifactResponse(BaseModel):
    projection_job_id: str
    object_id: str
    class_name: str
    content: str | None = None
    url: str | None = None
    raw: dict[str, object] | None = None


class GraphNodeResponse(BaseModel):
    node_id: str
    labels: list[str]
    properties: dict[str, object]


class GraphRelationshipResponse(BaseModel):
    relationship_id: str
    type: str
    start_node_id: str
    end_node_id: str
    properties: dict[str, object]


class GraphObservationResponse(BaseModel):
    observation: GraphNodeResponse | None = None
    nodes: list[GraphNodeResponse]
    relationships: list[GraphRelationshipResponse]
    cypher_browser_url: str | None = None


class DerivedStoreCleanupResponse(BaseModel):
    store: str
    success: bool
    deleted_count: int
    deleted_ids: list[str] = Field(default_factory=list)
    details: dict[str, object] = Field(default_factory=dict)
    error: str | None = None


class JournalDeleteResponse(BaseModel):
    entry_id: str
    cleanup: list[DerivedStoreCleanupResponse]


class UserDataDeleteResponse(BaseModel):
    user_id: str
    cleanup: list[DerivedStoreCleanupResponse]


class LocalDataWipeResponse(BaseModel):
    cleanup: list[DerivedStoreCleanupResponse]


class MemoryDebugResponse(BaseModel):
    entry: JournalEntryResponse
    projection_jobs: list[ProjectionJobResponse]
    weaviate_artifacts: list[WeaviateArtifactResponse]
    graph: GraphObservationResponse
    settings: MemorySettingsResponse
    links: dict[str, str]
