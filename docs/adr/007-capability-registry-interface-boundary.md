# ADR 007: Capability Registry and Interface Boundary

- Status: Accepted

## Context

Midas needs a clean way to extend the public `midas` core with `midas-pro` logic without introducing circular dependencies or making the public build unstable when the private package is missing.

## Decision

Implement a Capability Registry pattern. The `midas` core will define all extension points, such as `ICoachAgent`, using Python abstract base classes. A central registry will manage which implementation is active.

## Consequences

### Positive

- Logic stays strictly decoupled between the public core and the private extension layer.
- `midas` remains fully functional in a Core mode with local fallback implementations.

### Negative

- The architecture requires more upfront boilerplate because interfaces must be defined before implementations are added.

