from __future__ import annotations

from collections.abc import Mapping
from threading import Lock
from typing import Any, TypeVar


InterfaceT = TypeVar("InterfaceT")


class CapabilityRegistry:
    """Singleton registry for interface bindings and capability flags."""

    _instance: "CapabilityRegistry | None" = None
    _lock = Lock()

    def __new__(cls) -> "CapabilityRegistry":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._implementations = {}
                cls._instance._capabilities = {}
        return cls._instance

    def register(
        self,
        interface: type[InterfaceT],
        implementation: InterfaceT,
        *,
        feature_key: str | None = None,
        enabled: bool | None = None,
    ) -> None:
        self._implementations[interface] = implementation
        if feature_key is not None and enabled is not None:
            self._capabilities[feature_key] = enabled

    def resolve(self, interface: type[InterfaceT]) -> InterfaceT:
        implementation = self._implementations.get(interface)
        if implementation is None:
            raise KeyError(f"No implementation registered for {interface.__name__}")
        return implementation

    def is_pro_enabled(self, feature_key: str) -> bool:
        return self._capabilities.get(feature_key, False)

    def set_capability(self, feature_key: str, enabled: bool) -> None:
        self._capabilities[feature_key] = enabled

    def capability_map(self) -> dict[str, bool]:
        return dict(self._capabilities)

    def update_capabilities(self, values: Mapping[str, bool]) -> None:
        self._capabilities.update(values)

    def reset(self) -> None:
        self._implementations.clear()
        self._capabilities.clear()


def get_registry() -> CapabilityRegistry:
    return CapabilityRegistry()

