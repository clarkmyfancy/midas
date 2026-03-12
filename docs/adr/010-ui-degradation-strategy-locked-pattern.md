# ADR 010: UI Degradation Strategy (The "Locked" Pattern)

- Status: Accepted

## Context

Missing Pro features need to be handled gracefully so users understand what is unavailable and how to upgrade.

## Decision

Adopt the Locked UI pattern. When a Pro capability is missing, the web and iOS apps will show a disabled state or a Pro feature badge with an upgrade trigger.

## Consequences

### Positive

- Creates a clearer upgrade path and can improve conversion.
- Demonstrates product-level thinking in how premium capabilities are exposed.
- Gives users a more transparent experience than silently hiding features.

### Negative

- The UI must become aware of the capability map provided by the backend.

