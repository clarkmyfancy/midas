from pathlib import Path
import re
from collections.abc import AsyncIterator
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse


load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from app.agents.graph import astream_reflection_workflow
from app.schemas.capabilities import CapabilityMapResponse
from app.schemas.reflection import ReflectionRequest
from midas.core.entitlements import requires_entitlement, resolve_capabilities_for_user
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

TOKEN_PATTERN = re.compile(r"\S+\s*")


def iter_tokens(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(text) or [text]


async def stream_reflection_events(payload: ReflectionRequest) -> AsyncIterator[str]:
    async for chunk in astream_reflection_workflow(payload):
        for node_name, update in chunk.items():
            if node_name == "habit_analyst":
                for token in iter_tokens("Analyzing your journal against steps and sleep. "):
                    yield f"data: {token}\n\n"

            summary = update.get("summary")
            if isinstance(summary, str):
                for token in iter_tokens(summary):
                    yield f"data: {token}\n\n"


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/reflections")
async def create_reflection(payload: ReflectionRequest) -> StreamingResponse:
    return StreamingResponse(
        stream_reflection_events(payload),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/v1/capabilities", response_model=CapabilityMapResponse)
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
