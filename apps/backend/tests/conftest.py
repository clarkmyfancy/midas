import os

import pytest

os.environ["MIDAS_SKIP_DOTENV"] = "1"
os.environ["MIDAS_TEST_MODE"] = "1"
os.environ["MIDAS_LOAD_DOTENV_LOCAL"] = "0"
os.environ.pop("POSTGRES_URI", None)
os.environ.pop("WEAVIATE_URL", None)
os.environ.pop("NEO4J_HTTP_URL", None)
os.environ["OPENAI_API_KEY"] = ""

from langchain_core.messages import AIMessageChunk
import app.main as app_main
from midas.core.loader import load_capabilities
from midas.core.entitlements import reset_auth_storage_for_tests
import midas.core.insights as insights_module
import midas.core.projections as projections_module
from midas.core.memory import reset_memory_storage_for_tests
from tests.fakes import InMemoryTestGraphProjector, InMemoryTestWeaviateProjector


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
    InMemoryTestWeaviateProjector.reset()
    InMemoryTestGraphProjector.reset()
    load_capabilities(force=True)
    monkeypatch.setattr(projections_module, "WeaviateProjector", InMemoryTestWeaviateProjector)
    monkeypatch.setattr(projections_module, "GraphProjector", InMemoryTestGraphProjector)
    monkeypatch.setattr(insights_module, "WeaviateProjector", InMemoryTestWeaviateProjector)
    monkeypatch.setattr(insights_module, "GraphProjector", InMemoryTestGraphProjector)
    monkeypatch.setattr(app_main, "WeaviateProjector", InMemoryTestWeaviateProjector)
    monkeypatch.setattr(app_main, "GraphProjector", InMemoryTestGraphProjector)
    monkeypatch.setattr(
        "app.agents.graph.create_habit_analyst_chain",
        lambda _model: FakeHabitAnalystChain(),
    )
