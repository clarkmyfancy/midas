from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.agents.graph import ReflectionState


class BaseAgent(ABC):
    """Shared interface for graph-backed agents."""

    name: str

    @abstractmethod
    def run(self, state: "ReflectionState") -> dict:
        raise NotImplementedError

