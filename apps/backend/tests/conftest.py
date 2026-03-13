import pytest

from langchain_core.messages import AIMessageChunk


class FakeHabitAnalystChain:
    async def astream(self, _messages):
        for token in [
            "- Semantic drift: recovery signals stayed low despite upbeat journal framing.\n",
            "- Movement intention looks stronger than the biometric follow-through.\n",
            "- HRV and sleep suggest strain underneath the stated momentum.\n",
        ]:
            yield AIMessageChunk(content=token)


@pytest.fixture(autouse=True)
def stub_habit_analyst_chain(monkeypatch):
    monkeypatch.setattr(
        "app.agents.graph.create_habit_analyst_chain",
        lambda _model: FakeHabitAnalystChain(),
    )
