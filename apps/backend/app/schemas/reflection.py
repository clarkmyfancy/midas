from pydantic import BaseModel, Field


class ReflectionRequest(BaseModel):
    journal_entry: str = Field(..., min_length=1, description="Journal text to analyze.")
    goals: list[str] = Field(default_factory=list, description="Current goals or priorities.")


class ReflectionResponse(BaseModel):
    summary: str
    findings: list[str]
    trace: list[str]

