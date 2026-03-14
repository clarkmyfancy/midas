import asyncio

from langgraph.checkpoint.base import BaseCheckpointSaver

from app.agents.graph import astream_reflection_workflow, run_reflection_workflow
from app.schemas.reflection import ReflectionRequest


def test_reflection_workflow_returns_summary_and_trace() -> None:
    result = run_reflection_workflow(
        ReflectionRequest(
            journal_entry="I was distracted most of the day but managed a short workout.",
            goals=["Deep work", "Consistency"],
            steps=4200,
            sleep_hours=5.75,
            hrv_ms=38.0,
        )
    )

    assert "What stands out:" in result.summary
    assert result.findings
    assert len(result.trace) == 2
    assert result.trace[1].startswith("core_reflection_coach:")


def test_astream_reflection_workflow_skips_sync_only_checkpointer(monkeypatch) -> None:
    class SyncOnlyCheckpointer(BaseCheckpointSaver):
        pass

    async def collect_chunks() -> list[object]:
        chunks: list[object] = []
        async for chunk in astream_reflection_workflow(
            ReflectionRequest(
                journal_entry="I said I had energy, but I felt strained.",
                goals=["Protect recovery"],
            )
        ):
            chunks.append(chunk)
        return chunks

    monkeypatch.setattr("app.agents.graph.get_checkpointer", lambda: SyncOnlyCheckpointer())

    chunks = asyncio.run(collect_chunks())

    assert chunks
    assert any(
        isinstance(chunk, tuple)
        and len(chunk) == 2
        and chunk[0] == "custom"
        and isinstance(chunk[1], dict)
        and chunk[1].get("token")
        for chunk in chunks
    )
