# Semantic Drift Eval Pack

## Scenario Set

Use these five cases as the default regression pack.

1. Values mismatch
   - Journal entry: "I say deep work matters, but I spent most of today bouncing between tabs and avoiding the hard task."
   - Goals: `["Deep work", "Integrity"]`
   - Expected trace: `habit_analyst` then `core_reflection_coach` in Core mode
   - Expected behavior: name the distraction pattern without shaming and suggest one concrete behavior change

2. Energy tradeoff
   - Journal entry: "I was exhausted after work, skipped the gym, then took a short walk to reset instead."
   - Goals: `["Protect energy", "Stay active"]`
   - Expected behavior: acknowledge the tradeoff and avoid framing the day as a failure

3. Overcommitment
   - Journal entry: "I promised too many things again and now my calendar is full of obligations I do not want."
   - Goals: `["Focus", "Boundaries"]`
   - Expected behavior: identify overload, connect it to goal conflict, and recommend a boundary action

4. Identity drift
   - Journal entry: "I keep telling people I want to be calm and present, but my messages today were rushed and reactive."
   - Goals: `["Presence", "Calm leadership"]`
   - Expected behavior: connect identity language to observable behavior, not generic wellness advice

5. Avoidance loop
   - Journal entry: "I reorganized my notes for an hour instead of sending the proposal because I was afraid it was not ready."
   - Goals: `["Ship work", "Courage"]`
   - Expected behavior: identify avoidance disguised as preparation and recommend a small shipping action

## Rubric

- Empathy `0.0`: dismissive, preachy, or misreads the emotional context
- Empathy `0.5`: technically correct but emotionally thin
- Empathy `1.0`: accurately reflects the tension in the entry and gives actionable support without overreach

- Trajectory accuracy `1`: correct path, correct constraints, correct trace expectations, no made-up capabilities
- Trajectory accuracy `0`: wrong path, missing path, fabricated tools, fabricated Pro access, or advice that ignores the stated goals

## Judge Prompt Template

System prompt:

```text
You are grading an agent output for Midas. Score empathy from 0.0 to 1.0 and trajectory_accuracy as 0 or 1. Return strict JSON only.
```

User prompt template:

```json
{
  "scenario_id": "values-mismatch",
  "journal_entry": "...",
  "goals": ["..."],
  "expected_behavior": "...",
  "expected_trace": ["habit_analyst", "core_reflection_coach"],
  "actual_output": {
    "summary": "...",
    "findings": ["..."],
    "trace": ["..."]
  }
}
```

Expected judge response shape:

```json
{
  "empathy": 0.84,
  "trajectory_accuracy": 1,
  "notes": "Short explanation of the score.",
  "missed_expectations": ["Optional list"]
}
```
