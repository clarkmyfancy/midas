---
name: agent-evaluator
description: Evaluate Midas agent behavior with scenario-based judge workflows. Use when changing reflection logic, semantic-drift analysis, tool routing, prompt behavior, or agent orchestration and you need repeatable scoring instead of a single smoke test. Generate synthetic journal cases, run the target workflow, score the outputs with the rubric in `references/semantic-drift-eval.md`, and report aggregate failures before merging.
---

# Agent Evaluator

## Required Workflow

1. Name the target workflow, route, or agent under test.
2. Start with the five semantic-drift scenarios in `references/semantic-drift-eval.md`. Add more only if the change introduces a new failure mode.
3. Run the real Midas execution path. Prefer direct workflow or API execution over paraphrasing expected behavior.
4. Judge every output with the requested model. If the user names `o3-mini`, use it. Keep the rubric and response schema fixed across runs.
5. Score each case on empathy and trajectory accuracy, then summarize the mean score, worst case, and recurring failure pattern.
6. If the model called the wrong tools, hallucinated unavailable capabilities, or skipped the Core-versus-Pro boundary, call that out explicitly.

## Scoring Rules

- Score empathy on a continuous `0.0` to `1.0` scale.
- Score trajectory accuracy as `1` only when the workflow chose the right path, surfaced the right limits, and produced the expected trace/tool behavior for the case. Otherwise score `0`.
- Treat unsupported claims about Pro features, private tools, or non-existent retrieval as automatic trajectory failures.

## Reporting

- Report per-scenario scores in a compact table or JSON list.
- Include one concrete fix hypothesis for the lowest-scoring case.
- Keep raw prompts, scenario definitions, and judge outputs so a later run is comparable.

## Resource

- Load `references/semantic-drift-eval.md` for the scenario pack, rubric details, and the judge prompt template.
