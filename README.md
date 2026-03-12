# Midas

Midas is a monorepo for a private, multi-agent reflection system spanning FastAPI, Next.js, and SwiftUI.

## Repository Structure

- `apps/backend`: FastAPI service orchestrating agent workflows with LangGraph
- `apps/web`: Next.js dashboard consuming shared contracts
- `apps/ios`: SwiftUI starter app for the mobile client
- `packages/config`: shared TypeScript configuration
- `packages/types`: generated TypeScript types derived from backend Pydantic models
- `docs/adr`: architecture decision records

## Why a Monorepo

The repo uses a Turborepo workspace to keep API contracts, web UI, and mobile scaffolding close together while preserving a clean boundary for future private "Pro" agents. The accepted decision is documented in [docs/adr/001-repository-structure.md](docs/adr/001-repository-structure.md).

## Getting Started

### JavaScript workspace

```bash
pnpm install
pnpm generate:types
pnpm dev
```

### Backend

```bash
cd apps/backend
uv sync
uv run uvicorn app.main:app --reload
```

### iOS

```bash
cd apps/ios
xcodegen generate
```

