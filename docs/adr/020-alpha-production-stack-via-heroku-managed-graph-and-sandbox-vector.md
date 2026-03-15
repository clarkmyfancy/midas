# ADR 020: Alpha Production Stack via Heroku, Managed Graph, and Sandbox Vector Memory

- Status: Accepted

## Context

Midas currently runs locally with:

- a Next.js web app
- a FastAPI backend
- Postgres
- Weaviate
- Neo4j

The local repository includes a Docker Compose memory stack for Postgres, Weaviate, and Neo4j, but the intended alpha operator does not have an always-on server to self-host stateful services.

The alpha goal is narrower than a hardened production launch:

- get the product in front of real users quickly
- keep source-of-truth user data durable
- minimize infrastructure cost
- preserve the ability to recover derived memory systems from canonical Postgres records

The existing architecture already treats Postgres as the system of record and Weaviate plus Neo4j as rebuildable projections of canonical records.

## Decision

Adopt the following alpha production stack:

- frontend web app on Heroku
- backend API on a separate Heroku app
- canonical Postgres on Heroku Postgres
- graph memory on Neo4j Aura Free
- vector memory on a Weaviate Sandbox cluster

This is explicitly an alpha deployment posture rather than the final long-term production platform.

The deployment model prioritizes:

- fast launch without self-managed servers
- strong durability for canonical data in Postgres
- low-cost experimentation for graph and vector memory
- operational acceptance that Weaviate Sandbox is disposable and must be replayable from Postgres

Local development remains supported through the existing local Docker Compose stack and localhost app processes.

## Consequences

### Positive

- The product can be deployed without provisioning or maintaining an always-on VPS.
- Postgres remains on a managed service and continues to serve as the only canonical system of record.
- Neo4j and Weaviate can be tested in real user flows without immediately paying for higher-tier managed infrastructure.
- The architecture stays aligned with the existing principle that graph and vector stores are rebuildable projections.

### Negative

- The alpha stack mixes providers across multiple hosting surfaces and increases configuration complexity.
- Neo4j Aura Free and Weaviate Sandbox are not equivalent to hardened production infrastructure.
- Weaviate Sandbox should be treated as temporary and potentially disposable, which increases the importance of replay tooling and projection monitoring.
- The current codebase requires compatibility work before Neo4j Aura and Weaviate Cloud-hosted environments are fully supported.

## Alternatives Considered

- Keep everything local-only: rejected because it does not support external alpha users.
- Self-host Postgres, Weaviate, and Neo4j on a VPS: rejected for alpha because the operator does not have or want an always-on server to manage.
- Use Heroku for all stateful services: rejected because Weaviate and Neo4j are poor fits for Heroku dyno/container persistence.
- Delay graph and vector memory entirely: deferred, but not chosen because alpha feedback should include those product surfaces if they can be made compatible.

## Implementation Notes

- Postgres remains the only required durable store for successful writes.
- Replay and recovery paths for Weaviate and Neo4j should be treated as required alpha-readiness work.
- The alpha deployment should begin with a single backend instance until projection job claiming is made safe for horizontal scale.
- Local development defaults should continue pointing to localhost and the checked-in Docker Compose services unless production-specific environment variables are explicitly set.
