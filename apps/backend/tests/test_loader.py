from midas.core.loader import CoreFallbackAgent, load_capabilities
from midas.core.registry import get_registry
from midas.interfaces.agents import ReflectionCoachInterface


def test_loader_registers_core_fallback_when_pro_package_is_missing() -> None:
    registry = load_capabilities(force=True)
    coach = registry.resolve(ReflectionCoachInterface)

    assert isinstance(coach, CoreFallbackAgent)
    assert registry.is_pro_enabled("pro_analytics") is False


def test_registry_is_singleton() -> None:
    assert get_registry() is get_registry()
