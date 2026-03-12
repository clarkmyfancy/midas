from fastapi import FastAPI

from app.agents.graph import run_reflection_workflow
from app.schemas.reflection import ReflectionRequest, ReflectionResponse

app = FastAPI(
    title="Midas API",
    version="0.1.0",
    description="Backend scaffold for the Midas multi-agent reflection system.",
)


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/reflections", response_model=ReflectionResponse)
def create_reflection(payload: ReflectionRequest) -> ReflectionResponse:
    return run_reflection_workflow(payload)

