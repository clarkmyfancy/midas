# ADR 001: Repository Structure

- Status: Accepted

## Context

Midas needs to support a multi-platform product surface across iOS, web, and API while preserving a clean path for an Open Core monetization model on GitHub. The repository structure needs to maximize developer velocity, support shared contracts between the backend and frontend, and keep the proprietary "Pro" agent layer separate from the public core.

## Decision

Adopt a monorepo for the core Midas application, with shared packages for configuration and cross-platform types. Keep the public product surfaces and shared contracts in this repository, while isolating proprietary "Pro" agents and premium orchestration logic in a separate private repository.

## Consequences

### Positive

- Faster iteration on API contracts because backend and frontend changes can ship from one repository.
- Shared type generation reduces contract drift between FastAPI, Next.js, and future tooling.
- Sponsors can unlock Pro features through commercial distribution paths such as Polar.sh without exposing proprietary agent logic in the public repo.

### Negative

- CI/CD pipelines need path-filtering to avoid rebuilding the iOS app when only the web dashboard changes.
- Tooling complexity increases because the monorepo has to coordinate Python, TypeScript, and Swift workflows.

