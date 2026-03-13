from pydantic import BaseModel, Field


class ReflectionRequest(BaseModel):
    journal_entry: str = Field(..., min_length=1, description="Journal text to analyze.")
    goals: list[str] = Field(default_factory=list, description="Current goals or priorities.")
    steps: int | None = Field(default=None, ge=0, description="Daily step count to compare against the journal.")
    sleep_hours: float | None = Field(
        default=None,
        ge=0,
        description="Sleep duration in hours to compare against the journal.",
    )
    hrv_ms: float | None = Field(
        default=None,
        ge=0,
        description="Average heart rate variability in milliseconds for the recent observation window.",
    )


class ReflectionResponse(BaseModel):
    summary: str
    findings: list[str]
    trace: list[str]
