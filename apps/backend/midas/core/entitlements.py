from __future__ import annotations

from typing import Annotated

from fastapi import Header, HTTPException, status

from midas.core.loader import load_capabilities


class MockPolarService:
    """Temporary entitlement service until Polar.sh is wired in."""

    def has_entitlement(
        self,
        user_id: str | None,
        feature_key: str,
        entitlement_header: str | None = None,
    ) -> bool:
        if entitlement_header:
            values = {item.strip() for item in entitlement_header.split(",") if item.strip()}
            if feature_key in values or "pro" in values:
                return True

        return user_id in {"pro-user", "sponsor-user"}


polar_service = MockPolarService()


def resolve_capabilities_for_user(
    user_id: str | None,
    entitlement_header: str | None = None,
) -> dict[str, bool]:
    registry = load_capabilities()
    capabilities: dict[str, bool] = {}

    for feature_key, backend_available in registry.capability_map().items():
        entitled = polar_service.has_entitlement(user_id, feature_key, entitlement_header)
        capabilities[feature_key] = backend_available and entitled

    return capabilities


def requires_entitlement(feature_key: str):
    def dependency(
        x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
        x_entitlements: Annotated[str | None, Header(alias="X-Entitlements")] = None,
    ) -> None:
        registry = load_capabilities()
        if not registry.is_pro_enabled(feature_key):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"{feature_key} is not installed in this deployment",
            )

        if not polar_service.has_entitlement(x_user_id, feature_key, x_entitlements):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing entitlement for {feature_key}",
            )

    return dependency
