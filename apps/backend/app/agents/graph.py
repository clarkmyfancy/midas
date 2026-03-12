import operator
from typing import Annotated

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from app.agents.habit_analyst import HabitAnalystAgent
from app.agents.reflection_coach import ReflectionCoachAgent
from app.schemas.reflection import ReflectionRequest, ReflectionResponse


class ReflectionState(TypedDict):
    journal_entry: str
    goals: list[str]
    findings: Annotated[list[str], operator.add]
    summary: str
    trace: Annotated[list[str], operator.add]


def build_reflection_graph():
    workflow = StateGraph(ReflectionState)
    habit_analyst = HabitAnalystAgent()
    reflection_coach = ReflectionCoachAgent()

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

