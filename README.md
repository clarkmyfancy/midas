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

## Local Setup

This section is the canonical guide for getting Midas running on a fresh machine.

It is written for someone starting from scratch:

- you do not need a pre-existing database
- you do not need a private cloud environment
- you do not need anything from the original author’s computer

### What runs locally

When Midas is running in local development, there are five main pieces:

| Piece | Runs on | What it does |
| --- | --- | --- |
| Web app | `localhost:3000` | The UI for chatting with Midas, reviewing memory, and inspecting profile/data tools |
| Backend API | `localhost:8000` | The FastAPI service that accepts journal/reflection requests and orchestrates memory updates |
| Postgres | `localhost:5432` | The system of record for users, journal entries, chat threads, projection jobs, and clarification tasks |
| Weaviate | `localhost:8080` | Vector memory storage used for searchable memory artifacts and summaries |
| Neo4j | `localhost:7474` / `localhost:7687` | Graph memory storage used for people, projects, moods, and relationships between them |

The normal flow is:

1. You enter a reflection in the web UI.
2. The backend stores the canonical entry in Postgres.
3. Projection jobs derive vector artifacts in Weaviate and graph entities/relationships in Neo4j.
4. The UI can inspect all of that state through the memory and review pages.

### 1. Install prerequisites

Required tools:

- `git`
- `pnpm`
- `uv`
- Python `3.13`
- Docker with Compose support

You can use any package manager you prefer as long as those tools are installed and available on your shell path.

Minimum version expectations:

- Node capable of running the current `pnpm` workspace
- Python `3.13`
- Docker daemon running locally

Sanity checks:

```bash
git --version
pnpm --version
uv --version
python3.13 --version
docker info
docker compose version
```

If `python3.13` is not installed yet, install it with `uv`:

```bash
uv python install 3.13
```

### 2. Clone the repository

```bash
git clone <your-fork-or-repo-url> midas
cd midas
```

### 3. Install workspace dependencies

From the repository root:

```bash
pnpm install
```

This installs the JavaScript and TypeScript dependencies for the monorepo. The backend Python dependencies are handled by `uv` when you run backend commands.

### 4. Create the backend environment file

The backend reads local configuration from `apps/backend/.env`.

Create it from the checked-in example:

```bash
cp apps/backend/.env.example apps/backend/.env
```

The default example is already configured for the local Docker services started by this repository.

Important variables:

- `OPENAI_API_KEY`
  - Needed for live LLM-backed reflection/chat behavior and model-based extraction.
  - If this is missing, some behavior falls back to heuristics and some chat/reflection quality degrades.
- `POSTGRES_URI`
  - Tells the backend how to connect to the local Postgres container.
- `WEAVIATE_URL`
  - Tells the backend where the local Weaviate service lives.
- `WEAVIATE_API_KEY`
  - Optional authentication token for hosted Weaviate environments such as Cloud or Sandbox.
  - Leave this empty for the local anonymous Docker service.
- `NEO4J_HTTP_URL`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`
  - Tells the backend how to write graph memory into Neo4j.
- `MIDAS_AUTO_PROJECT`
  - `1` means every new reflection/journal entry will automatically project into Weaviate and Neo4j.
  - `0` means entries are stored first and projection jobs must be run later.
- `MIDAS_AUTO_PROJECT_WEAVIATE`, `MIDAS_AUTO_PROJECT_NEO4J`
  - Optional per-store overrides for automatic projection behavior.
  - If unset, both inherit from `MIDAS_AUTO_PROJECT`.
  - This keeps local behavior unchanged while allowing production to auto-run Weaviate and Neo4j independently.

If you want live model output, add your key:

```bash
OPENAI_API_KEY="your_key_here"
```

### 5. Start the local data services

Make sure Docker is running, then from the repository root run:

```bash
pnpm memory:up
```

This starts three containers:

- Postgres
- Weaviate
- Neo4j

Default local Neo4j credentials:

- Username: `neo4j`
- Password: `midasdevpassword`

If you want to inspect the container definitions directly, they live in [docker-compose.yml](docker-compose.yml).

### 6. Start the app

From the repository root run:

```bash
pnpm dev:site
```

This starts:

- the FastAPI backend in `apps/backend`
- the Next.js web app in `apps/web`

By default, `pnpm dev:site` sets `MIDAS_AUTO_PROJECT=1`, so new entries automatically propagate into Weaviate and Neo4j unless you override that environment variable yourself.

### 7. Open the local surfaces

Once the services are up, these URLs are the main local touch points:

- Web app: `http://localhost:3000`
- Reflect/chat page: `http://localhost:3000/reflect`
- Memory inspector: `http://localhost:3000/memory`
- Profile page: `http://localhost:3000/profile`
- Backend OpenAPI docs: `http://127.0.0.1:8000/docs`
- Neo4j Browser: `http://localhost:7474/browser/`
- Weaviate schema: `http://localhost:8080/v1/schema`
- Weaviate objects: `http://localhost:8080/v1/objects`

### 8. First-run walkthrough

If you want to confirm the whole stack is healthy:

1. Open `http://localhost:3000/login`
2. Register a local user account
3. Go to `http://localhost:3000/reflect`
4. Send a short reflection or journal-style message
5. Open `http://localhost:3000/memory`
6. Confirm that you can see:
   - the canonical journal entry in Postgres-backed state
   - projection jobs
   - Weaviate artifacts
   - Neo4j graph output

If `MIDAS_AUTO_PROJECT=0`, use the `Run Projections` control from the Memory page to process the queued jobs.

### 9. What success looks like

If local setup is working correctly:

- the web app loads at `localhost:3000`
- the backend docs load at `127.0.0.1:8000/docs`
- submitting a reflection creates a journal entry
- projection jobs move from pending to completed
- Weaviate shows `MemoryArtifact` objects
- Neo4j shows `Observation` and `Entity` nodes

### 10. Common local tasks

Generate shared TypeScript contracts after backend schema changes:

```bash
pnpm generate:types
```

Run the backend tests:

```bash
cd apps/backend
UV_CACHE_DIR=/tmp/uv-cache uv run pytest
```

Run the web validation:

```bash
pnpm --filter @midas/web build
pnpm --filter @midas/web typecheck
```

### 11. Troubleshooting

If `pnpm memory:up` fails:

- confirm Docker is running
- confirm `docker info` works
- confirm ports `5432`, `7474`, `7687`, and `8080` are not already occupied

If the web app loads but reflections fail:

- check that the backend is running on `127.0.0.1:8000`
- check `apps/backend/.env`
- if you expect LLM-backed output, check that `OPENAI_API_KEY` is set

If entries appear in Postgres-backed views but not in Weaviate or Neo4j:

- check whether `MIDAS_AUTO_PROJECT` is `0`
- use the Memory page to run projection jobs manually
- inspect backend logs for projection errors

If you want to clear local memory data without deleting user accounts:

- use the Profile page’s dev-only data wipe tools

### 12. Package-specific docs

If you only need one part of the system:

- Backend details: [apps/backend/README.md](apps/backend/README.md)
- Web details: [apps/web/README.md](apps/web/README.md)
- iOS details: [apps/ios/README.md](apps/ios/README.md)
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
