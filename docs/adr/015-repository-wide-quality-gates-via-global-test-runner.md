# ADR 015: Repository-Wide Quality Gates via global-test-runner

- Status: Accepted

## Context

In an Open Core model, a change that works in the Pro environment might break the Core environment. Midas needs to verify that both remain functional before any code is published.

## Decision

Deploy a `global-test-runner` skill as a mandatory pre-publish gate.

## Rationale

This skill executes a Core-only build and a full-stack build in parallel. It runs unit, integration, and evaluation tests across all repositories to ensure the public `midas` repo is never in a broken state for contributors or potential employers.

## Consequences

### Positive

- Provides high confidence in the public credibility of the core repo.

### Negative

- Significantly increases CI/CD pipeline duration and resource consumption.
