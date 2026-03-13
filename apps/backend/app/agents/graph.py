import operator
from collections.abc import AsyncIterator, Callable
from typing import Annotated

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from app.schemas.reflection import ReflectionRequest, ReflectionResponse
from midas.core.loader import load_capabilities
from midas.core.registry import CapabilityRegistry
from midas.interfaces.agents import ReflectionCoachInterface


HABIT_ANALYST_SYSTEM_PROMPT = """You are Midas's habit analyst.

Analyze how well the user's journal entry aligns with their goals, daily steps, sleep, and heart rate variability.
Look for reinforcing patterns, signs of friction, and mismatches between the narrative and biometrics.
Return 2 to 4 concise findings. Each finding should be a short sentence fragment, not a paragraph.
If step, sleep, or HRV data is missing, explicitly note that limited context in one finding and rely on the journal and goals for the rest.
"""


class HabitAnalysis(BaseModel):
    findings: list[str] = Field(
        ...,
        min_length=2,
        max_length=4,
        description="Concise findings about alignment between the journal entry, goals, and biometrics.",
    )


class ReflectionState(TypedDict):
    journal_entry: str
    goals: list[str]
    steps: int | None
    sleep_hours: float | None
    hrv_ms: float | None
    findings: Annotated[list[str], operator.add]
    summary: str
    trace: Annotated[list[str], operator.add]


def create_habit_analyst_chain():
    return ChatOpenAI(model="gpt-4o-mini", temperature=0).with_structured_output(
        HabitAnalysis
    )


def run_habit_analyst_node(state: ReflectionState) -> dict[str, list[str]]:
    analyst_chain = create_habit_analyst_chain()
    prompt = "\n".join(
        [
            f"Journal entry: {state['journal_entry']}",
            f"Goals: {', '.join(state['goals']) if state['goals'] else 'None provided'}",
            f"Steps: {state['steps'] if state['steps'] is not None else 'missing'}",
            (
                "Sleep hours: "
                f"{state['sleep_hours'] if state['sleep_hours'] is not None else 'missing'}"
            ),
            f"HRV (ms): {state['hrv_ms'] if state['hrv_ms'] is not None else 'missing'}",
        ]
    )
    analysis = analyst_chain.invoke(
        [
            SystemMessage(content=HABIT_ANALYST_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]
    )

    return {
        "findings": analysis.findings,
        "trace": ["habit_analyst: analyzed journal entry against goals, steps, sleep, and hrv"],
    }


def resolve_next_node(registry: CapabilityRegistry) -> Callable[[ReflectionState], str]:
    def _resolve(_: ReflectionState) -> str:
        return registry.resolve(ReflectionCoachInterface).name

    return _resolve


def build_reflection_graph():
    workflow = StateGraph(ReflectionState)
    registry = load_capabilities()
    reflection_coach = registry.resolve(ReflectionCoachInterface)

    workflow.add_node("habit_analyst", run_habit_analyst_node)
    workflow.add_node(reflection_coach.name, reflection_coach.run)

    workflow.add_edge(START, "habit_analyst")
    workflow.add_conditional_edges("habit_analyst", resolve_next_node(registry))
    workflow.add_edge(reflection_coach.name, END)

    return workflow.compile()


def build_reflection_input(payload: ReflectionRequest) -> ReflectionState:
    return {
        "journal_entry": payload.journal_entry,
        "goals": payload.goals,
        "steps": payload.steps,
        "sleep_hours": payload.sleep_hours,
        "hrv_ms": payload.hrv_ms,
        "findings": [],
        "summary": "",
        "trace": [],
    }


async def astream_reflection_workflow(
    payload: ReflectionRequest,
) -> AsyncIterator[dict[str, dict[str, object]]]:
    graph = build_reflection_graph()
    async for chunk in graph.astream(build_reflection_input(payload), stream_mode="updates"):
        yield chunk


def run_reflection_workflow(payload: ReflectionRequest) -> ReflectionResponse:
    graph = build_reflection_graph()
    result = graph.invoke(build_reflection_input(payload))
    return ReflectionResponse(
        summary=result["summary"],
        findings=result["findings"],
        trace=result["trace"],
    )
