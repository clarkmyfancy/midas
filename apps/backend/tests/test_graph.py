from app.agents.graph import run_reflection_workflow
from app.schemas.reflection import ReflectionRequest


def test_reflection_workflow_returns_summary_and_trace() -> None:
    result = run_reflection_workflow(
        ReflectionRequest(
            journal_entry="I was distracted most of the day but managed a short workout.",
            goals=["Deep work", "Consistency"],
        )
    )

    assert "detected the following themes" in result.summary
    assert result.findings
    assert len(result.trace) == 2
