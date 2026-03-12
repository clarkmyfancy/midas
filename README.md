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

- Keep the core local-first iOS, web, and backend platform public
- Generate and share contracts across the monorepo to maximize development speed
- Keep proprietary "Pro" agents and premium orchestration logic in a separate private repository
- Support hosted offerings, premium features, and App Store monetization on top of the public core

The repository structure decision is documented in [docs/adr/001-repository-structure.md](docs/adr/001-repository-structure.md).

## Implementation Roadmap

### Phase 1: Synthetic testing

Generate 90 days of synthetic journal and HealthKit-style data to test the habit analysis loop safely before using personal data.

### Phase 2: Security sandbox

Run agent workflows in isolated environments for imported file analysis and higher-trust execution boundaries.

### Phase 3: Personal pivot

Replace synthetic data with real personal data and document the transition from development to a trusted production-grade personal system.

## Repository Structure

- `apps/backend`: FastAPI service orchestrating agent workflows with LangGraph
- `apps/web`: Next.js dashboard consuming shared contracts
- `apps/ios`: SwiftUI starter app for the mobile client
- `packages/config`: shared TypeScript configuration
- `packages/types`: generated TypeScript types derived from backend Pydantic models
- `docs/adr`: architecture decision records

See [PROJECT_SPEC.md](PROJECT_SPEC.md) for the fuller high-level problem specification.

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
