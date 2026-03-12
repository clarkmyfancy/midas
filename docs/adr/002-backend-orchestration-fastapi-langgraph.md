# ADR 002: Backend Orchestration with FastAPI and LangGraph

- Status: Accepted

## Context

Personal coaching requires stateful, multi-turn loops where the AI remembers previous context and can branch logic based on biometric data.

## Decision

Adopt FastAPI for the web layer and LangGraph for agentic orchestration.

## Consequences

### Positive

- LangGraph provides native checkpointers, including PostgreSQL-backed persistence, which helps solve the deployment gap when a session is interrupted or resumed.
- FastAPI provides a straightforward, production-ready web layer for exposing agent workflows and structured contracts.

### Negative

- LangGraph introduces a steeper learning curve than linear chain-based abstractions.

## Alternatives Considered

- CrewAI: Better for autonomous swarms, but offers less control over low-level state transitions.
- Simple OpenAI API calls: Simpler to start with, but lack resumability and durable workflow state.

