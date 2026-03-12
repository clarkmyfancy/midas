# Midas Backend

FastAPI backend for the Midas multi-agent AI system.

## Structure

- `app/agents/`: agent nodes and LangGraph orchestration
- `app/tools/`: backend tools exposed to agents
- `app/schemas/`: Pydantic contracts for the API and workflows
- `scripts/generate_types.py`: Pydantic-to-TypeScript generation for the monorepo
- `tests/`: API and graph tests

## Getting started

```bash
uv sync
uv run uvicorn app.main:app --reload
```

## Generate shared types

```bash
uv run python scripts/generate_types.py
```

## Test

```bash
uv run pytest
```
