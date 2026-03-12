# Midas Web

Next.js dashboard for the Midas reflection system.

## Key Concepts

- Uses generated contracts from `@midas/types`
- Includes a `FeatureGate` component for locked Pro experiences
- Expects a capability map from the backend `GET /api/v1/capabilities` endpoint

## Getting Started

From the repo root:

```bash
pnpm install
pnpm generate:types
pnpm --filter @midas/web dev
```

## Validation

```bash
pnpm --filter @midas/web typecheck
pnpm --filter @midas/web build
```

