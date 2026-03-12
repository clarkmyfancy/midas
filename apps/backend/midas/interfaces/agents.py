from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any


class BaseAgent(ABC):
    """Base contract for LangGraph-compatible agents."""

    name: str

    @abstractmethod
    def run(self, state: Mapping[str, Any]) -> dict[str, Any]:
        """Execute a graph node and return the partial state update."""


class ReflectionCoachInterface(BaseAgent, ABC):
    """Extension point for reflection coach implementations."""

