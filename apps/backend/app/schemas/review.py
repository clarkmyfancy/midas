from datetime import datetime

from pydantic import BaseModel

from app.schemas.journal import (
    ClarificationTaskResponse,
    GraphObservationResponse,
    JournalEntryResponse,
    WeaviateArtifactResponse,
)


class ReviewFindingResponse(BaseModel):
    title: str
    detail: str
    evidence: list[str]


class ReviewStatResponse(BaseModel):
    label: str
    value: str


class WeeklyReviewResponse(BaseModel):
    summary: str
    generated_at: datetime
    window_days: int
    findings: list[ReviewFindingResponse]
    stats: list[ReviewStatResponse]
    entries: list[JournalEntryResponse]
    memory_highlights: list[WeaviateArtifactResponse]
    graph: GraphObservationResponse
    clarifications: list[ClarificationTaskResponse]
    warnings: list[str]
