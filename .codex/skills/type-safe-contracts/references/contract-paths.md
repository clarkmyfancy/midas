# Contract Paths

## Current Commands

From the repository root:

```bash
pnpm generate:types
pnpm --filter @midas/web typecheck
pnpm --filter @midas/web build
```

Backend-only regeneration:

```bash
pnpm --filter @midas/backend generate:types
```

Direct backend command:

```bash
cd apps/backend
uv run python scripts/generate_types.py
```

## Current Source and Output Paths

- Source schemas: `apps/backend/app/schemas/`
- Generator entrypoint: `apps/backend/scripts/generate_types.py`
- Generator model registry: `apps/backend/app/schemas/__init__.py`
- Generated TypeScript: `packages/types/src/generated/reflection.ts`
- Generated TS barrel: `packages/types/src/generated/index.ts`
- Shared TS package entrypoint: `packages/types/src/index.ts`
- Web consumer examples: `apps/web/app/page.tsx`, `apps/web/README.md`

## Current Gap

- No `openapi-typescript` command is configured in `package.json`.
- No Swift Codable or OpenAPI generator path is configured under `apps/ios`.
- If a task requires cross-platform codegen beyond TypeScript, add that infrastructure first and record the exact command and output path here.
