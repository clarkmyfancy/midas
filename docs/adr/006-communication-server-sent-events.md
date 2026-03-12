# ADR 006: Communication via Server-Sent Events (SSE)

- Status: Accepted

## Context

AI responses take time to generate. Users need to see tokens streaming in real time to maintain trust and perceived performance.

## Decision

Implement Server-Sent Events (SSE) for all agent-to-client communication.

## Consequences

### Positive

- SSE is simpler than WebSockets for token streaming.
- It has native browser and iOS-friendly support patterns and handles reconnections well.

### Negative

- SSE is unidirectional and only supports server-to-client streaming.

## Alternatives Considered

- WebSockets: More flexible, but heavier than necessary for straightforward token streaming.
- Long polling: Easier to understand, but creates poorer UX and weaker perceived responsiveness.

