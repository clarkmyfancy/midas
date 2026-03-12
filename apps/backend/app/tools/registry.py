from collections.abc import Callable

from app.tools.journal_tools import extract_behavioral_signals, summarize_goal_alignment

ToolFn = Callable[..., object]

TOOLS: dict[str, ToolFn] = {
    "extract_behavioral_signals": extract_behavioral_signals,
    "summarize_goal_alignment": summarize_goal_alignment,
}

