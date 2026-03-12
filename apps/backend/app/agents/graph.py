import operator
from typing import Annotated

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from app.agents.habit_analyst import HabitAnalystAgent
from app.schemas.reflection import ReflectionRequest, ReflectionResponse
from midas.core.loader import load_capabilities
from midas.interfaces.agents import ReflectionCoachInterface


class ReflectionState(TypedDict):
    journal_entry: str
    goals: list[str]
    findings: Annotated[list[str], operator.add]
    summary: str
    trace: Annotated[list[str], operator.add]


def build_reflection_graph():
    workflow = StateGraph(ReflectionState)
    habit_analyst = HabitAnalystAgent()
    registry = load_capabilities()
    reflection_coach = registry.resolve(ReflectionCoachInterface)

    workflow.add_node(habit_analyst.name, habit_analyst.run)
    workflow.add_node(reflection_coach.name, reflection_coach.run)

    workflow.add_edge(START, habit_analyst.name)
    workflow.add_edge(habit_analyst.name, reflection_coach.name)
    workflow.add_edge(reflection_coach.name, END)

    return workflow.compile()


def run_reflection_workflow(payload: ReflectionRequest) -> ReflectionResponse:
    graph = build_reflection_graph()
    result = graph.invoke(
        {
            "journal_entry": payload.journal_entry,
            "goals": payload.goals,
            "findings": [],
            "summary": "",
            "trace": [],
        }
    )
    return ReflectionResponse(
        summary=result["summary"],
        findings=result["findings"],
        trace=result["trace"],
    )
