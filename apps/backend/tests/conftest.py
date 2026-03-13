import os

import pytest

from langchain_core.messages import AIMessageChunk
from midas.core.entitlements import reset_auth_storage_for_tests


os.environ.pop("POSTGRES_URI", None)
os.environ["MIDAS_LOAD_DOTENV_LOCAL"] = "0"


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
    reset_auth_storage_for_tests()
    monkeypatch.setattr(
        "app.agents.graph.create_habit_analyst_chain",
        lambda _model: FakeHabitAnalystChain(),
    )
