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

## Codex Guardrails

This repository now includes local Codex skills under `.codex/skills` to keep architecture and release work consistent.

- `midas-architect`: enforce the open-core boundary before implementation begins
- `agent-evaluator`: define judge-based evaluation workflows for agent behavior
- `secure-sandboxing`: standardize E2B plus Presidio handling for sensitive analysis
- `type-safe-contracts`: regenerate and validate shared contracts after schema changes
- `midas-publish-guard`: run the current automated test suite before pushing branches or updating `main`

The current pre-push command is:

```bash
sh .codex/skills/midas-publish-guard/scripts/run_publish_checks.sh
```

The corresponding architectural decisions are documented in `docs/adr/011` through `docs/adr/015`.

## Local Onboarding

This section is the fastest way to get the full local site running and inspectable on a fresh machine.

### 1. Prerequisites

Required:

- `uv`
- `pnpm`
- Python `3.13`
- Docker Desktop or another running Docker daemon

Optional:

- `xcodegen`
- Xcode command line tools / full Xcode for the iOS app

On macOS with Homebrew:

```bash
brew install uv pnpm xcodegen
uv python install 3.13
```

### 2. Clone and install dependencies

From the repository root:

```bash
cd /path/to/Midas
pnpm install
```

### 3. Create the backend environment file

Create `apps/backend/.env` from the checked-in example:

```bash
cp apps/backend/.env.example apps/backend/.env
```

The default local values in `apps/backend/.env.example` already point at the local Docker services.

Important variables:

- `OPENAI_API_KEY`
  - Required if you want live reflection generation through the OpenAI-backed habit analyst.
  - Without it, the memory projection system can still run, but live reflection/chat quality will be limited or fail where OpenAI is required.
- `MIDAS_AUTO_PROJECT`
  - `1` means journal entries and reflection writes will automatically fan out into Weaviate and Neo4j in local dev.
  - `0` means journal entries queue projection jobs and you run them manually from the Memory page.
  - The checked-in local default is now `1`.

If you want live model responses, edit `apps/backend/.env` and set:

```bash
OPENAI_API_KEY="your_key_here"
```

### 4. Start Docker Desktop

Start Docker Desktop before trying to boot the memory services:

```bash
open -a "Docker"
```

Wait for Docker to finish starting, then confirm the daemon is healthy:

```bash
docker info
```

### 5. Start the local data services

From the repository root:

```bash
pnpm memory:up
```

This starts:

- Postgres on `localhost:5432`
- Weaviate on `localhost:8080`
- Neo4j on `localhost:7474` and `localhost:7687`

Neo4j local credentials:

- Username: `neo4j`
- Password: `midasdevpassword`

### 6. Start the local site

From the repository root:

```bash
pnpm dev:site
```

This runs:

- FastAPI backend
- Next.js web app

`pnpm dev:site` also exports `MIDAS_AUTO_PROJECT=1` by default unless you explicitly override it before the command.

### 7. Open the local surfaces

Once the dev servers are up, open:

- Web app: `http://localhost:3000`
- Memory inspector: `http://localhost:3000/memory`
- Backend OpenAPI docs: `http://127.0.0.1:8000/docs`
- Neo4j Browser: `http://localhost:7474/browser/`
- Weaviate schema: `http://localhost:8080/v1/schema`
- Weaviate objects: `http://localhost:8080/v1/objects`

### 8. First-run workflow

After the app is running:

1. Open `http://localhost:3000/login`
2. Register a local account
3. Open `http://localhost:3000`
4. If you want to inspect storage internals, open `http://localhost:3000/memory`
5. Create a journal entry from the Memory page
6. Watch the Memory page settle the projection jobs automatically
7. If you need to retry failed jobs, use the `Run Projections` button
8. If you want to test data cleanup, use `Delete Selected Entry`
9. Inspect:
   - canonical journal record
   - queued/completed projection jobs
   - Weaviate artifacts
   - Neo4j observation graph
   - current memory mode (`Auto project: on|off`)

## Alternative Local Commands

### Run backend only

```bash
cd apps/backend
uv sync --python 3.13
MIDAS_AUTO_PROJECT=1 env UV_CACHE_DIR=/tmp/uv-cache uv run uvicorn app.main:app --reload
```

### Run web only

```bash
cd /path/to/Midas
pnpm --filter @midas/web dev
```

### Run iOS app

```bash
cd apps/ios
xcodegen generate
open Midas.xcodeproj
```

## Verification

These commands were run successfully against the current repository state:

### Backend

```bash
cd apps/backend
env UV_CACHE_DIR=/tmp/uv-cache uv run pytest
env UV_CACHE_DIR=/tmp/uv-cache uv run python -m compileall app tests scripts midas
```

### Web

```bash
cd /path/to/Midas
pnpm generate:types
pnpm --filter @midas/web build
pnpm --filter @midas/web typecheck
```

### iOS

```bash
cd apps/ios
xcodegen generate
xcodebuild -project Midas.xcodeproj -scheme Midas -sdk iphonesimulator -derivedDataPath .derived-data CODE_SIGNING_ALLOWED=NO build
```

## Troubleshooting

### `pnpm memory:up` says the Docker daemon is not running

Start Docker Desktop:

```bash
open -a "Docker"
docker info
```

Then rerun:

```bash
pnpm memory:up
```

### Backend errors mention missing Postgres columns like `completed_at`

This means your local Postgres table was created before the latest schema fields were added. Restart the backend so it can run the lightweight startup migration:

```bash
pnpm dev:site
```

If the backend was already running, stop it and start it again.

### Web typecheck fails because `.next/types` files are missing

Build the web app first, then rerun typecheck:

```bash
pnpm --filter @midas/web build
pnpm --filter @midas/web typecheck
```

### Reflection/chat is up but the model is not responding

Check that `OPENAI_API_KEY` is set in `apps/backend/.env`, then restart the backend.

### Entries are being created but the graph or vector artifacts never appear

Check the Memory page first:

- `http://localhost:3000/memory`
- confirm it says `Auto project: on`
- confirm the job cards for the selected entry moved from `pending` to `completed`

If auto projection is off, either:

```bash
MIDAS_AUTO_PROJECT=1 pnpm dev:site
```

or set this in `apps/backend/.env`:

```bash
MIDAS_AUTO_PROJECT="1"
```

If jobs are still pending or failed, you can force a manual retry from the UI or with:

```bash
curl -X POST http://127.0.0.1:8000/v1/projection-jobs/run \
  -H "Authorization: Bearer <your_access_token>"
```

### You deleted an entry and want to confirm the cleanup really happened

After deleting from `http://localhost:3000/memory`, verify:

- the entry disappeared from the journal list
- the debug payload cleared for that entry
- the delete status message shows cleanup counts for both `weaviate` and `neo4j`
- the related Weaviate objects are gone from `http://localhost:8080/v1/objects`
- the related Neo4j observation node is gone from `http://localhost:7474/browser/`

Before publishing new code to a remote, run:

```bash
sh .codex/skills/midas-publish-guard/scripts/run_publish_checks.sh
```
