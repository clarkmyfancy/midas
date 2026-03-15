from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from midas.core.memory import (
    ClarificationTaskRecord,
    JournalEntryRecord,
    list_clarification_tasks_for_user,
    list_journal_entries_for_user,
)


WEAVIATE_REVIEW_PREFERENCE = {
    "weaviate_semantic_summary": 0,
    "weaviate_episode_summary": 1,
    "weaviate_raw_journal_entry": 2,
    "weaviate_journal_memory": 3,
}


@dataclass(frozen=True)
class ReviewFinding:
    title: str
    detail: str
    evidence: list[str]


@dataclass(frozen=True)
class ReviewStat:
    label: str
    value: str


@dataclass(frozen=True)
class WeeklyReviewResult:
    summary: str
    generated_at: datetime
    window_days: int
    findings: list[ReviewFinding]
    stats: list[ReviewStat]
    entries: list[JournalEntryRecord]
    clarifications: list[ClarificationTaskRecord]
    warnings: list[str]


def _format_average(values: list[float], suffix: str) -> str:
    if not values:
        return "n/a"
    return f"{sum(values) / len(values):.1f}{suffix}"


def build_weekly_review(*, user_id: str, window_days: int = 7) -> WeeklyReviewResult:
    generated_at = datetime.now(UTC)
    cutoff = generated_at - timedelta(days=window_days)
    all_entries = list_journal_entries_for_user(user_id)
    entries = [entry for entry in all_entries if entry.created_at >= cutoff]
    warnings: list[str] = []

    clarifications = list_clarification_tasks_for_user(user_id, status="pending")

    goal_counter = Counter(goal for entry in entries for goal in entry.goals)
    total_goals = sum(len(entry.goals) for entry in entries)

    findings: list[ReviewFinding] = []
    if clarifications:
        findings.append(
            ReviewFinding(
                title="Pending clarifications",
                detail=f"There are {len(clarifications)} names or aliases that still need your confirmation.",
                evidence=[task.prompt for task in clarifications[:3]],
            )
        )
    if entries:
        findings.append(
            ReviewFinding(
                title="Consistency",
                detail=f"You captured {len(entries)} entries in the last {window_days} days.",
                evidence=[
                    entry.journal_entry
                    for entry in sorted(entries, key=lambda entry: entry.created_at, reverse=True)[:3]
                ],
            )
        )
    if goal_counter:
        findings.append(
            ReviewFinding(
                title="Explicit priorities",
                detail="These priorities came up most often in what you wrote down this week.",
                evidence=[f"{goal}: {count} entries" for goal, count in goal_counter.most_common(3)],
            )
        )

    sleep_values = [entry.sleep_hours for entry in entries if entry.sleep_hours is not None]
    hrv_values = [entry.hrv_ms for entry in entries if entry.hrv_ms is not None]
    step_values = [float(entry.steps) for entry in entries if entry.steps is not None]
    average_sleep = sum(sleep_values) / len(sleep_values) if sleep_values else None
    average_hrv = sum(hrv_values) / len(hrv_values) if hrv_values else None

    if average_sleep is not None or average_hrv is not None:
        biometrics_evidence: list[str] = []
        if average_sleep is not None:
            biometrics_evidence.append(f"Average sleep: {average_sleep:.1f}h")
        if average_hrv is not None:
            biometrics_evidence.append(f"Average HRV: {average_hrv:.1f}ms")
        findings.append(
            ReviewFinding(
                title="Biometrics snapshot",
                detail="Your weekly reflection includes the biometrics you logged alongside your entries.",
                evidence=biometrics_evidence,
            )
        )

    stats = [
        ReviewStat(label="Entries", value=str(len(entries))),
        ReviewStat(label="Named goals", value=str(total_goals)),
        ReviewStat(label="Avg sleep", value=_format_average(sleep_values, "h")),
        ReviewStat(label="Avg HRV", value=_format_average(hrv_values, "ms")),
        ReviewStat(label="Avg steps", value=_format_average(step_values, "")),
        ReviewStat(label="Pending clarifications", value=str(len(clarifications))),
    ]

    if findings:
        summary_parts = [finding.detail for finding in findings[:3]]
    elif entries:
        summary_parts = [f"You logged {len(entries)} entries in the last {window_days} days."]
    else:
        summary_parts = ["No recent review signals were found yet."]
    summary = " ".join(summary_parts)

    return WeeklyReviewResult(
        summary=summary,
        generated_at=generated_at,
        window_days=window_days,
        findings=findings,
        stats=stats,
        entries=entries,
        clarifications=clarifications,
        warnings=warnings,
    )
