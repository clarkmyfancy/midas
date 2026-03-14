# Midas Web

Next.js frontend for chat, review, memory inspection, and profile/data controls.

If you are starting from scratch, use the root onboarding guide first:

- [../../README.md](../../README.md)

That guide explains how the web app connects to the backend and local memory services.

## What this app does

The web app is the main local developer surface. It includes:

- the reflect/chat experience
- the memory inspection page
- the weekly review UI
- profile and local data management controls

It consumes generated contracts from `@midas/types` and expects the backend capability map from `GET /api/v1/capabilities`.

## Local web-only startup

From the repository root:

```bash
pnpm install
pnpm generate:types
pnpm --filter @midas/web dev
```

The web app expects the backend to be available at the configured API base URL. In local development that defaults to `http://127.0.0.1:8000`.

## Validation

```bash
pnpm --filter @midas/web build
pnpm --filter @midas/web typecheck
```
