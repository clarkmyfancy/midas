# Midas Backend

FastAPI backend for the Midas reflection, memory, and graph pipeline.

If you are starting from scratch, use the root onboarding guide first:

- [../../README.md](../../README.md)

That guide explains how the backend fits together with Postgres, Weaviate, Neo4j, and the web app.

## What this app does

The backend is the system coordinator. It:

- accepts journal and reflection requests from the clients
- stores canonical records in Postgres
- runs the reflection workflow
- creates and executes projection jobs for Weaviate and Neo4j
- exposes the API contracts consumed by the web app

## Important directories

- `app/`: FastAPI routes, schemas, and agent workflow entrypoints
- `midas/core/`: memory stores, projection logic, capability loading, entitlements
- `midas/interfaces/`: public extension interfaces for the open-core boundary
- `scripts/generate_types.py`: backend-to-TypeScript contract generation
- `tests/`: backend test suite

## Local backend-only startup

From `apps/backend`:

```bash
uv python install 3.13
uv sync --python 3.13
uv run uvicorn app.main:app --reload
```

This assumes:

- you already created `apps/backend/.env`
- Postgres, Weaviate, and Neo4j are already running if you want the full memory pipeline

## Useful backend endpoints

- `GET /docs`: OpenAPI / Swagger UI
- `GET /api/v1/capabilities`: capability map returned to clients
- `POST /v1/reflections`: reflection/chat entrypoint
- `GET /v1/clarifications`: pending clarification prompts
- `POST /v1/projection-jobs/run`: manually run queued projection jobs

## Generate shared types

From `apps/backend`:

```bash
uv run python scripts/generate_types.py
```

From the repository root:

```bash
pnpm generate:types
```

## Test

From `apps/backend`:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest
```

From the repository root, the publish guard runs the broader project checks:

```bash
sh .codex/skills/midas-publish-guard/scripts/run_publish_checks.sh
```
