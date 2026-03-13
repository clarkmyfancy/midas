"""Pydantic models for API and workflow contracts."""

from app.schemas.auth import (
    AuthLoginRequest,
    AuthRegisterRequest,
    AuthTokenResponse,
    AuthUserResponse,
)
from app.schemas.capabilities import CapabilityMapResponse
from app.schemas.reflection import ReflectionRequest, ReflectionResponse

SCHEMA_MODELS = [
    ReflectionRequest,
    ReflectionResponse,
    CapabilityMapResponse,
    AuthRegisterRequest,
    AuthLoginRequest,
    AuthUserResponse,
    AuthTokenResponse,
]

__all__ = [
    "AuthLoginRequest",
    "AuthRegisterRequest",
    "AuthTokenResponse",
    "AuthUserResponse",
    "CapabilityMapResponse",
    "ReflectionRequest",
    "ReflectionResponse",
    "SCHEMA_MODELS",
]
