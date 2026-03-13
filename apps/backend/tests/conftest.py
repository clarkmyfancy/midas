import pytest

from app.agents.graph import HabitAnalysis


class FakeHabitAnalystChain:
    def invoke(self, _messages):
        return HabitAnalysis(
            findings=[
                "Journal shows follow-through on movement despite low energy",
                "Biometric context is limited, so confidence is based mostly on the journal entry",
            ]
        )


@pytest.fixture(autouse=True)
def stub_habit_analyst_chain(monkeypatch):
    monkeypatch.setattr(
        "app.agents.graph.create_habit_analyst_chain",
        lambda: FakeHabitAnalystChain(),
    )
