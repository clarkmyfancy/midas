from typing import Annotated

from fastapi import Depends, FastAPI, Header

from app.agents.graph import run_reflection_workflow
from app.schemas.capabilities import CapabilityMapResponse
from app.schemas.reflection import ReflectionRequest, ReflectionResponse
from midas.core.entitlements import requires_entitlement, resolve_capabilities_for_user
from midas.core.loader import load_capabilities

app = FastAPI(
    title="Midas API",
    version="0.1.0",
    description="Backend scaffold for the Midas multi-agent reflection system.",
)

load_capabilities()


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/reflections", response_model=ReflectionResponse)
def create_reflection(payload: ReflectionRequest) -> ReflectionResponse:
    return run_reflection_workflow(payload)


@app.get("/api/v1/capabilities", response_model=CapabilityMapResponse)
def capability_map(
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_entitlements: Annotated[str | None, Header(alias="X-Entitlements")] = None,
) -> CapabilityMapResponse:
    return CapabilityMapResponse(
        capabilities=resolve_capabilities_for_user(x_user_id, x_entitlements)
    )


@app.get("/api/v1/pro/analytics")
def pro_analytics_status(
    _: Annotated[None, Depends(requires_entitlement("pro_analytics"))],
) -> dict[str, str]:
    return {"status": "enabled", "feature": "pro_analytics"}
