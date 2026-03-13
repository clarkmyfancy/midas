import os
from pathlib import Path
from collections.abc import AsyncIterator
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header
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


@app.post("/api/v1/reflections")
@app.post("/v1/reflections")
async def create_reflection(
    payload: ReflectionRequest,
    user: Annotated[AuthUser, Depends(get_current_user)],
) -> StreamingResponse:
    thread_suffix = payload.thread_id or "reflection"
    resolved_payload = payload.model_copy(
        update={"thread_id": f"user:{user.id}:{thread_suffix}"}
    )
    return StreamingResponse(
        stream_reflection_events(resolved_payload),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
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
