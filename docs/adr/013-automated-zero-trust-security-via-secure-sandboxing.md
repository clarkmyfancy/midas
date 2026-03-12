# ADR 013: Automated Zero-Trust Security via secure-sandboxing

- Status: Accepted

## Context

Executing AI-generated code on user HealthKit and Calendar data is a massive security risk. Midas needs a defense-in-depth posture that treats the model as untrusted compute.

## Decision

Standardize environment isolation through a `secure-sandboxing` skill.

## Rationale

The skill automates the setup of E2B Firecracker microVMs and enforces Microsoft Presidio PII scrubbing before any data enters the sandbox. This keeps user privacy intact even if the agent is compromised by prompt injection.

## Consequences

### Positive

- Hardware-level isolation for all analysis tasks.
- Sub-second execution starts keep the sandbox practical for interactive workflows.

### Negative

- Requires API keys and usage tracking for the E2B platform.
