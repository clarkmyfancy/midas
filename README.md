# Midas

Midas is a private, local-first, multi-agent personal growth system designed to detect and reduce semantic drift: the gap between who a person intends to become and the person their behavior, health data, and calendar patterns suggest they are becoming.

This repository is both a product foundation and a portfolio-grade example of secure, AI-augmented systems design across iPhone, web, and API surfaces.

## Why This Matters

Modern personal growth tools are fragmented.

- Passive trackers like HealthKit and Oura produce raw metrics without explaining why they change.
- Active trackers like journaling apps capture reflection but rarely audit patterns, inconsistencies, or blind spots over time.

Midas bridges those worlds by synthesizing subjective intent with objective reality.

- Subjective intent: journals, reflections, goals, stated priorities
- Objective reality: biometrics, calendar activity, behavioral patterns

The goal is not just to log data. The goal is to help a user understand whether their actions are actually aligned with the person they want to become.

## Product Vision

Midas operates as a hybrid ecosystem across iPhone and the web.

### iPhone

- Native SwiftUI interface for multi-turn conversational journaling
- Siri-triggered reflection sessions via App Intents
- HealthKit ingestion for steps, sleep stages, and HRV
- On-device privacy proxy for PII masking before high-reasoning analysis

### Web

- Semantic drift dashboard showing alignment between goals and activity
- Deep weekly reflections generated from long-horizon memory
- Knowledge graph of mental models, recurring blockers, and behavioral loops

## Technical Direction

The current monorepo is structured around a staff-level systems blueprint.

| Component | Technology | Rationale |
| --- | --- | --- |
| Mobile | SwiftUI + HealthKit + App Intents | Native access to Apple security boundaries and biometrics |
| Web | Next.js | Product dashboard and visualization layer |
| API | FastAPI + LangGraph | Stateful orchestration for agent workflows |
| Memory | Weaviate or Milvus | Long-horizon vector retrieval and safe migrations |
| Agents | Specialized multi-agent architecture | Reduced context noise and clearer responsibilities |
| Security | E2B sandboxes + Microsoft Presidio | Isolated execution and edge PII redaction |
| Infrastructure | Pulumi or Terraform | Infrastructure as code for reproducible environments |
| MLOps | LangSmith + Arize Phoenix | Evaluation, tracing, and RAG observability |

## Open Core Strategy

Midas is intended to support an open-source core with commercial upside.

- Keep the core local-first iOS, web, and backend platform public.
- Generate and share contracts across the monorepo to maximize development speed.
- Keep proprietary `midas-pro` agents and premium orchestration logic in a separate private repository.
- Support hosted offerings, premium features, and App Store monetization on top of the public core.

The repository structure decision is documented in [docs/adr/001-repository-structure.md](docs/adr/001-repository-structure.md).

## Capability Boundary

The backend now implements an explicit open-core boundary.

- Public interfaces live under `apps/backend/midas/interfaces`.
- Active implementations are selected through the capability registry in `apps/backend/midas/core/registry.py`.
- `apps/backend/midas/core/loader.py` attempts to load `midas_pro` and falls back to Core implementations when that package is absent.
- Runtime entitlements are checked through a mock Polar-compatible guard in `apps/backend/midas/core/entitlements.py`.
- `GET /api/v1/capabilities` returns the feature map consumed by the web and iOS clients.

This keeps the public repo fully runnable in Core mode while preserving a clean injection path for private Pro packages later.

## Repository Structure

- `apps/backend`: FastAPI service orchestrating agent workflows with LangGraph
- `apps/web`: Next.js dashboard consuming shared contracts and capability gates
- `apps/ios`: SwiftUI starter app with a Pro-gated view helper
- `packages/config`: shared TypeScript configuration
- `packages/types`: generated TypeScript types derived from backend Pydantic models
- `docs/adr`: architecture decision records

See [PROJECT_SPEC.md](PROJECT_SPEC.md) for the fuller high-level problem specification.

## Prerequisites

- `uv`
- `pnpm`
- `xcodegen`
- Python `3.13`
- Xcode command line tools / Xcode for iOS builds

On macOS with Homebrew:

```bash
brew install uv pnpm xcodegen
uv python install 3.13
```

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
uv sync --python 3.13
uv run uvicorn app.main:app --reload
```

### iOS

```bash
cd apps/ios
xcodegen generate
open Midas.xcodeproj
```

## Verification

These commands were run successfully against the current repository state:

```bash
cd apps/backend
uv sync --python 3.13
uv run pytest
uv run python -c "from fastapi.testclient import TestClient; from app.main import app; client = TestClient(app); print(client.get('/api/v1/capabilities').json())"
```

```bash
pnpm install
pnpm --filter @midas/web typecheck
pnpm --filter @midas/web build
pnpm generate:types
```

```bash
cd apps/ios
xcodegen generate
xcodebuild -project Midas.xcodeproj -scheme Midas -sdk iphonesimulator -derivedDataPath .derived-data CODE_SIGNING_ALLOWED=NO build
```

