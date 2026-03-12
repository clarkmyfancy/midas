# ADR 012: Probabilistic MLOps via agent-evaluator

- Status: Accepted

## Context

Traditional deterministic unit tests cannot measure stochastic qualities like coaching empathy or hallucination rate in agentic workflows.

## Decision

Implement an `agent-evaluator` skill using the LLM-as-a-judge pattern.

## Rationale

The skill automates the creation of synthetic test cases and uses high-reasoning models such as `o3-mini` to grade agent trajectories against defined rubrics. This brings the same rigor to AI behavior that the codebase already expects for standard code.

## Consequences

### Positive

- Catches behavioral regressions that standard CI would miss.

### Negative

- Evaluation runs incur token costs and add latency to the CI pipeline.
