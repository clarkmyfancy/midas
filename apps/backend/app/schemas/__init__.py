"""Pydantic models for API and workflow contracts."""

from app.schemas.auth import (
    AuthLoginRequest,
    AuthRegisterRequest,
    AuthTokenResponse,
    AuthUserResponse,
)
from app.schemas.capabilities import CapabilityMapResponse
from app.schemas.journal import (
    JournalEntryCreateRequest,
    JournalEntryListResponse,
    JournalEntryResponse,
    JournalIngestResponse,
    MemoryDebugResponse,
    GraphNodeResponse,
    GraphObservationResponse,
    GraphRelationshipResponse,
    ProjectionJobListResponse,
    ProjectionJobResponse,
    ProjectionRunResponse,
    WeaviateArtifactResponse,
)
from app.schemas.reflection import ReflectionRequest, ReflectionResponse

SCHEMA_MODELS = [
    ReflectionRequest,
    ReflectionResponse,
    CapabilityMapResponse,
    AuthRegisterRequest,
    AuthLoginRequest,
    AuthUserResponse,
    AuthTokenResponse,
    JournalEntryCreateRequest,
    JournalEntryResponse,
    ProjectionJobResponse,
    JournalIngestResponse,
    JournalEntryListResponse,
    ProjectionJobListResponse,
    ProjectionRunResponse,
    WeaviateArtifactResponse,
    GraphNodeResponse,
    GraphRelationshipResponse,
    GraphObservationResponse,
    MemoryDebugResponse,
]

__all__ = [
    "AuthLoginRequest",
    "AuthRegisterRequest",
    "AuthTokenResponse",
    "AuthUserResponse",
    "CapabilityMapResponse",
    "JournalEntryCreateRequest",
    "JournalEntryListResponse",
    "JournalEntryResponse",
    "JournalIngestResponse",
    "MemoryDebugResponse",
    "GraphNodeResponse",
    "GraphObservationResponse",
    "GraphRelationshipResponse",
    "ProjectionJobListResponse",
    "ProjectionJobResponse",
    "ProjectionRunResponse",
    "WeaviateArtifactResponse",
    "ReflectionRequest",
    "ReflectionResponse",
    "SCHEMA_MODELS",
]
