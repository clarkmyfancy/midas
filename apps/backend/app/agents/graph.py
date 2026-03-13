import asyncio
import atexit
import os
import operator
import re
from collections.abc import AsyncIterator, Callable
from typing import Annotated
from uuid import uuid4

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from app.schemas.reflection import ReflectionRequest, ReflectionResponse
from midas.core.loader import load_capabilities
from midas.core.registry import CapabilityRegistry
from midas.interfaces.agents import ReflectionCoachInterface

try:
    from langgraph.checkpoint.postgres import PostgresSaver
except ImportError:  # pragma: no cover - optional dependency in local dev until installed
    PostgresSaver = None


HABIT_ANALYST_SYSTEM_PROMPT = """You are Midas's habit analyst.

Detect semantic drift between the user's stated intentions in the journal and the synthetic health snapshot they provided.
Semantic drift means the story they tell about their day does not fully match their recovery, activity, or physiological signals.
Prioritize mismatches between the journal narrative and health metrics, then note one reinforcing pattern if it exists.
Return exactly 3 bullet findings, one per line, each starting with "- ".
Keep each finding under 18 words.
Do not add a heading, numbering, or conclusion.
"""


class ReflectionState(TypedDict):
    journal_entry: str
    goals: list[str]
    steps: int | None
    sleep_hours: float | None
    hrv_ms: float | None
    findings: Annotated[list[str], operator.add]
    summary: str
    trace: Annotated[list[str], operator.add]


_checkpointer_context = None
_checkpointer = None


def resolve_habit_analyst_model(registry: CapabilityRegistry) -> str:
    return "gpt-4o" if registry.is_pro_enabled("pro_analytics") else "gpt-4o-mini"


def create_habit_analyst_chain(model: str) -> ChatOpenAI:
    return ChatOpenAI(model=model, temperature=0)


def extract_chunk_text(content: object) -> str:
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)

    return ""


def parse_analyst_findings(raw_text: str) -> list[str]:
    findings: list[str] = []

    for line in raw_text.splitlines():
        cleaned = re.sub(r"^\s*[-*•\d.)\s]+", "", line).strip()
        if cleaned:
            findings.append(cleaned)

    if findings:
        return findings[:3]

    fallback = raw_text.strip()
    return [fallback] if fallback else ["Health signals did not produce a usable semantic drift analysis"]


def make_habit_analyst_node(
    registry: CapabilityRegistry,
) -> Callable[[ReflectionState], AsyncIterator[dict[str, list[str]]] | dict[str, list[str]]]:
    async def _run(state: ReflectionState) -> dict[str, list[str]]:
        model = resolve_habit_analyst_model(registry)
        analyst_chain = create_habit_analyst_chain(model)
        writer = get_stream_writer()
        streamed_text: list[str] = []

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

        async for chunk in analyst_chain.astream(
            [
                SystemMessage(content=HABIT_ANALYST_SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ]
        ):
            token = extract_chunk_text(chunk.content)
            if not token:
                continue
            streamed_text.append(token)
            writer({"source": "habit_analyst", "token": token})

        findings = parse_analyst_findings("".join(streamed_text))

        return {
            "findings": findings,
            "trace": [f"habit_analyst: streamed semantic drift analysis with {model}"],
        }

    return _run


def resolve_next_node(registry: CapabilityRegistry) -> Callable[[ReflectionState], str]:
    def _resolve(_: ReflectionState) -> str:
        return registry.resolve(ReflectionCoachInterface).name

    return _resolve


def get_checkpointer():
    global _checkpointer_context, _checkpointer

    if _checkpointer is not None:
        return _checkpointer

    db_uri = os.getenv("POSTGRES_URI")
    if not db_uri or PostgresSaver is None:
        return None

    _checkpointer_context = PostgresSaver.from_conn_string(db_uri)
    _checkpointer = _checkpointer_context.__enter__()
    _checkpointer.setup()
    atexit.register(_checkpointer_context.__exit__, None, None, None)
    return _checkpointer


def supports_async_checkpointing(checkpointer: object) -> bool:
    aget_tuple = getattr(type(checkpointer), "aget_tuple", None)
    return aget_tuple is not None and aget_tuple is not BaseCheckpointSaver.aget_tuple


def build_reflection_graph(*, for_async: bool = False):
    workflow = StateGraph(ReflectionState)
    registry = load_capabilities()
    reflection_coach = registry.resolve(ReflectionCoachInterface)

    workflow.add_node("habit_analyst", make_habit_analyst_node(registry))
    workflow.add_node(reflection_coach.name, reflection_coach.run)

    workflow.add_edge(START, "habit_analyst")
    workflow.add_conditional_edges("habit_analyst", resolve_next_node(registry))
    workflow.add_edge(reflection_coach.name, END)

    checkpointer = get_checkpointer()
    if checkpointer is None:
        return workflow.compile()

    if for_async and not supports_async_checkpointing(checkpointer):
        return workflow.compile()

    return workflow.compile(checkpointer=checkpointer)


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


def build_reflection_config(payload: ReflectionRequest) -> dict[str, dict[str, str]]:
    return {
        "configurable": {
            "thread_id": payload.thread_id or str(uuid4()),
        }
    }


async def astream_reflection_workflow(
    payload: ReflectionRequest,
) -> AsyncIterator[object]:
    graph = build_reflection_graph(for_async=True)
    async for chunk in graph.astream(
        build_reflection_input(payload),
        config=build_reflection_config(payload),
        stream_mode=["custom", "updates"],
    ):
        yield chunk


def run_reflection_workflow(payload: ReflectionRequest) -> ReflectionResponse:
    graph = build_reflection_graph()
    result = asyncio.run(
        graph.ainvoke(
            build_reflection_input(payload),
            config=build_reflection_config(payload),
        )
    )
    return ReflectionResponse(
        summary=result["summary"],
        findings=result["findings"],
        trace=result["trace"],
    )
