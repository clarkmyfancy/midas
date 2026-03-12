# ADR 011: Automated Open-Core Enforcement via midas-architect

- Status: Accepted

## Context

Maintaining a strict boundary between public `midas` and private `midas-pro` is a high-cognitive-load task. Manual reviews are prone to leaky abstractions where private logic is accidentally hard-coded into the public core.

## Decision

Deploy a `midas-architect` skill that acts as a mandatory pre-coding auditor.

## Rationale

This skill enforces the Capability Registry pattern and ensures all new features are defined by interfaces in `midas.interfaces` before implementation begins. It prevents the AI from proposing direct imports of `midas-pro` into public modules.

## Consequences

### Positive

- Guarantees the public repo remains runnable as a standalone portfolio piece.

### Negative

- Adds one mandatory verification step for the AI agent during feature planning.
