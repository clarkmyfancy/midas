from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from midas.core.registry import get_registry
from midas.interfaces.agents import ReflectionCoachInterface


class CoreFallbackAgent(ReflectionCoachInterface):
    name = "core_reflection_coach"

    def run(self, state: Mapping[str, Any]) -> dict[str, Any]:
        findings = list(state.get("findings", []))
        journal_entry = str(state.get("journal_entry", "")).strip()
        if findings:
            summary = "What stands out: " + " ".join(findings)
        elif journal_entry:
            summary = f"What stands out is the tension inside: {journal_entry}"
        else:
            summary = "What stands out is still unclear from this entry."

        summary += " Stay with the part that feels most charged or unresolved."
        return {
            "summary": summary,
            "trace": [f"{self.name}: generated core fallback reflection summary"],
        }


_loaded = False


def load_capabilities(*, force: bool = False):
    global _loaded

    registry = get_registry()
    if _loaded and not force:
        return registry

    registry.reset()
    registry.update_capabilities(
        {
            "pro_analytics": False,
            "weekly_reflection": False,
            "mental_model_graph": False,
        }
    )

    try:
        from midas_pro.agents import ProReflectionCoach  # type: ignore[import-not-found]
    except ImportError:
        registry.register(
            ReflectionCoachInterface,
            CoreFallbackAgent(),
            feature_key="pro_analytics",
            enabled=False,
        )
    else:
        registry.register(
            ReflectionCoachInterface,
            ProReflectionCoach(),
            feature_key="pro_analytics",
            enabled=True,
        )
        registry.update_capabilities(
            {
                "weekly_reflection": True,
                "mental_model_graph": True,
            }
        )

    _loaded = True
    return registry
