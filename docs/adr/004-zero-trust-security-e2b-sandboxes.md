# ADR 004: Zero-Trust Security via E2B Sandboxes

- Status: Accepted

## Context

The Habit Analyst needs to execute Python scripts to analyze user CSV files such as HealthKit exports. Running AI-generated code directly on the host is a critical security risk.

## Decision

Use E2B Firecracker microVMs to sandbox all code execution.

## Consequences

### Positive

- Firecracker-backed isolation provides a stronger security boundary than container-only approaches.
- Sub-second cold starts keep the security layer practical for interactive analysis flows.

### Negative

- The sandbox boundary adds roughly 300 milliseconds of latency to analysis tasks.

## Alternatives Considered

- Docker: Easier to adopt, but provides weaker isolation for hostile or AI-generated execution.
- Local subprocess execution: Operationally simple, but creates an unacceptable risk of host compromise.

