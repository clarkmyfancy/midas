# ADR 014: Type-Safe Cross-Platform Contracts via type-safe-contracts

- Status: Accepted

## Context

API drift between the Python backend, Next.js web dashboard, and SwiftUI iOS app is a primary source of runtime crashes in monorepos.

## Decision

Implement a `type-safe-contracts` skill to automate schema synchronization.

## Rationale

This skill manages the glue code by automatically running `openapi-ts` and Swift code generators whenever Pydantic models change. It ensures that the iOS and web apps stay in lock-step with the API definition.

## Consequences

### Positive

- Eliminates manual type definition work.
- Provides instant feedback on breaking changes across platforms.

### Negative

- Requires local environment setup for Node.js and Swift tooling within the monorepo.
