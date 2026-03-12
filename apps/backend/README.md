# Midas Backend

FastAPI backend for the Midas multi-agent AI system.

## Key Concepts

- `app/`: FastAPI app, LangGraph workflow, schemas, and core agents
- `midas/interfaces/`: public extension interfaces for open-core boundaries
- `midas/core/registry.py`: singleton capability registry
- `midas/core/loader.py`: optional `midas_pro` loader with Core fallbacks
- `midas/core/entitlements.py`: mock Polar-style entitlement guard
- `scripts/generate_types.py`: Pydantic-to-TypeScript generation for the monorepo
- `tests/`: runtime and loader coverage

## Runtime Notes

- The backend is pinned to Python `3.13` for compatibility with the current LangGraph and LangChain stack.
- The service is expected to run in Core mode when `midas_pro` is not installed.
- `GET /api/v1/capabilities` exposes the capability map used by the clients.
- `GET /api/v1/pro/analytics` is guarded by `requires_entitlement("pro_analytics")`.
- Open-core planning and boundary enforcement are documented in `docs/adr/007` and `docs/adr/011`.

## Getting Started

```bash
uv python install 3.13
uv sync --python 3.13
uv run uvicorn app.main:app --reload
```

## Generate Shared Types

```bash
uv run python scripts/generate_types.py
```

Or from the monorepo root:

```bash
pnpm generate:types
```

## Test

```bash
uv run pytest
```

From the repository root, the publish guard runs the same automated suite via:

```bash
sh .codex/skills/midas-publish-guard/scripts/run_publish_checks.sh
```

## Smoke Check

```bash
uv run python -c "from fastapi.testclient import TestClient; from app.main import app; client = TestClient(app); print(client.get('/health').json()); print(client.get('/api/v1/capabilities').json())"
```
