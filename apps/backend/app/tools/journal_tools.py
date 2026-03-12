def extract_behavioral_signals(journal_entry: str) -> list[str]:
    lowered = journal_entry.lower()
    signals: list[str] = []

    if "tired" in lowered or "exhausted" in lowered:
        signals.append("energy appears constrained")
    if "focus" in lowered or "distracted" in lowered:
        signals.append("attention may be fragmented")
    if "workout" in lowered or "walk" in lowered:
        signals.append("movement is present in the routine")

    if not signals:
        signals.append("behavioral signals are limited in the current entry")

    return signals


def summarize_goal_alignment(goals: list[str], signals: list[str]) -> str:
    if not goals:
        return "no explicit goals were provided for alignment analysis"

    return (
        f"alignment review completed for {len(goals)} goals using "
        f"{len(signals)} detected behavioral signals"
    )

