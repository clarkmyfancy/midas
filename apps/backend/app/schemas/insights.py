from datetime import datetime

from pydantic import BaseModel


class InsightStatResponse(BaseModel):
    label: str
    value: str


class InsightCardResponse(BaseModel):
    id: str
    category: str
    title: str
    summary: str
    severity: str
    confidence: float
    evidence: list[str]
    related_entities: list[str]
    source_types: list[str]


class InsightSectionResponse(BaseModel):
    id: str
    title: str
    description: str
    cards: list[InsightCardResponse]


class InsightsResponse(BaseModel):
    summary: str
    generated_at: datetime
    window_days: int
    sections: list[InsightSectionResponse]
    stats: list[InsightStatResponse]
    warnings: list[str]
