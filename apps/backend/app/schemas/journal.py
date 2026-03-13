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


class MemoryDebugResponse(BaseModel):
    entry: JournalEntryResponse
    projection_jobs: list[ProjectionJobResponse]
    weaviate_artifacts: list[WeaviateArtifactResponse]
    graph: GraphObservationResponse
    links: dict[str, str]
