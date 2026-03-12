# ADR 008: Secure Dependency Injection via Private Registries

- Status: Accepted

## Context

Installing private code directly through Git URLs is fragile in production and can leak repository tokens in build logs or deployment systems.

## Decision

Use the GitHub private package registry to distribute `midas-pro` as versioned Python wheels and NPM packages.

## Consequences

### Positive

- Supports semantic version pinning instead of depending on a moving branch head.
- Reduces the chance that a breaking change on `main` takes down production.
- Produces cleaner, safer build logs by avoiding direct tokenized Git installs.

### Negative

- `midas-pro` now needs a CI/CD publishing step before new versions can be consumed by `midas`.

