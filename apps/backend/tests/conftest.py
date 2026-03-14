import os

import pytest

from langchain_core.messages import AIMessageChunk
from midas.core.entitlements import reset_auth_storage_for_tests
from midas.core.memory import reset_memory_storage_for_tests


os.environ.pop("POSTGRES_URI", None)
os.environ["MIDAS_LOAD_DOTENV_LOCAL"] = "0"
os.environ["OPENAI_API_KEY"] = ""


class FakeHabitAnalystChain:
    async def astream(self, _messages):
        for token in [
            "- You describe pushing through strain instead of naming it directly.\n",
            "- Work pressure seems to be crowding out recovery.\n",
            "- The entry points to a tension you have not really resolved yet.\n",
        ]:
            yield AIMessageChunk(content=token)


@pytest.fixture(autouse=True)
def stub_habit_analyst_chain(monkeypatch):
    reset_auth_storage_for_tests()
    reset_memory_storage_for_tests()
    monkeypatch.setattr(
        "app.agents.graph.create_habit_analyst_chain",
        lambda _model: FakeHabitAnalystChain(),
    )
