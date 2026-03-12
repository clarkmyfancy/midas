from app.agents.base import BaseAgent
from app.tools.journal_tools import extract_behavioral_signals, summarize_goal_alignment


class HabitAnalystAgent(BaseAgent):
    name = "habit_analyst"

    def run(self, state: dict) -> dict:
        entry = state["journal_entry"]
        goals = state["goals"]
        signals = extract_behavioral_signals(entry)
        alignment = summarize_goal_alignment(goals, signals)
        findings = [*signals, alignment]

        return {
            "findings": findings,
            "trace": [f"{self.name}: analyzed journal entry against {len(goals)} goals"],
        }

