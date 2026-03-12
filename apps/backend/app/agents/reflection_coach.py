from app.agents.base import BaseAgent


class ReflectionCoachAgent(BaseAgent):
    name = "reflection_coach"

    def run(self, state: dict) -> dict:
        findings = state["findings"]
        summary = (
            "Midas detected the following themes: "
            + "; ".join(findings)
            + ". Recommended next step: choose one behavior to reinforce this week."
        )

        return {
            "summary": summary,
            "trace": [f"{self.name}: generated reflection summary"],
        }

