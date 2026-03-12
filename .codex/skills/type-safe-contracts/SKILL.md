---
name: type-safe-contracts
description: Keep Midas backend and client contracts aligned. Use when changing Pydantic schemas, API response models, capability payloads, or any shared contract consumed by the web or iOS apps. Regenerate the shared TypeScript contracts with the repo’s existing commands, verify downstream consumers, and do not claim Swift contract regeneration unless a real generator exists in this repository.
---

# Type-Safe Contracts

## Required Workflow

1. If the change touches `apps/backend/app/schemas` or `SCHEMA_MODELS`, regenerate contracts immediately.
2. Run `pnpm generate:types` from the repository root, or `pnpm --filter @midas/backend generate:types` if you only need the backend generator.
3. Review the generated output under `packages/types/src/generated`.
4. Validate consumers with `pnpm --filter @midas/web typecheck` and, when UI code changed, `pnpm --filter @midas/web build`.
5. Check whether the iOS app has a real generator or checked-in Codable models for the changed contract. In the current repo, no Swift contract generator is configured. Do not claim iOS regeneration unless you add one in the same change.

## Current Constraints

- The repository currently ships a custom Pydantic-to-TypeScript generator at `apps/backend/scripts/generate_types.py`.
- The generated barrel lives at `packages/types/src/generated/index.ts` and is re-exported by `packages/types/src/index.ts`.
- `apps/web` consumes the generated contracts through `@midas/types`.
- `apps/ios` currently has no OpenAPI, Swift Codable, or schema generation pipeline checked in.

## Failure Handling

- If the schema changed but generated files did not, verify that `SCHEMA_MODELS` includes the new model.
- If a user asks for `openapi-ts` or Swift regeneration, treat that as missing infrastructure unless you add the generator and config paths in the same task.
- Never hand-edit generated files to mask a schema mismatch.

## Resource

- Load `references/contract-paths.md` for the exact current commands and file paths.
