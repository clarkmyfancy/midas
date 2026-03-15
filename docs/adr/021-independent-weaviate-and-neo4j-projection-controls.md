# ADR 021: Independent Weaviate and Neo4j Projection Controls

- Status: Accepted

## Context

Midas currently exposes a single coarse environment switch for projection behavior:

- `MIDAS_AUTO_PROJECT`

That switch controls whether journal ingestion automatically runs downstream projection work at all.

This is too coarse for the planned alpha deployment.

The graph and vector stores have different operational risk profiles:

- Neo4j Aura Free may remain available while Weaviate Sandbox is degraded or expired
- Weaviate may need to be disabled temporarily without affecting canonical writes or graph projection
- local development may still want all projections enabled together by default

The architecture already treats Weaviate and Neo4j as separate rebuildable projections derived from Postgres, so they should be independently controllable at runtime.

## Decision

Replace the single coarse projection control with independent controls for automatic projection behavior.

The system should support separate runtime toggles for:

- automatic Weaviate projection
- automatic Neo4j projection

The intended operating model is:

- canonical Postgres writes always proceed
- each derived projection can be enabled or disabled independently
- disabled projections are backfilled later through explicit replay tooling rather than silently depending on a single all-or-nothing switch

Local development should remain easy:

- local defaults may keep both projection types enabled
- the new controls must preserve the current local developer experience unless a developer explicitly changes them

## Consequences

### Positive

- Operators can keep ingestion live even when one derived memory system is degraded.
- Alpha environments can selectively enable only the external systems that are ready.
- Replay and backfill flows become more explicit because disabled projections are treated as an operational state rather than an exceptional failure.
- The deployment can evolve incrementally from Postgres-only to partial projections to the full stack.

### Negative

- Configuration surface area increases.
- Projection orchestration logic becomes slightly more complex because enablement must be evaluated per projection type.
- Operational tooling must distinguish between intentionally disabled projections and true failed projections.

## Alternatives Considered

- Keep a single `MIDAS_AUTO_PROJECT` switch: rejected because it does not support partial availability or staged rollout.
- Hard-disable one projection type in code for alpha: rejected because it creates an unnecessary branch in behavior and makes later rollout harder.
- Always queue all projection jobs but skip execution when disabled: rejected because it blurs the difference between intended deferral and actual failures.

## Implementation Notes

- Projection enablement should be evaluated when jobs are created so intentionally disabled projection types are not automatically queued.
- Separate replay tooling should exist for backfilling disabled projection types later.
- Monitoring and admin tooling should report per-projection-type status.
- The legacy all-or-nothing switch may be retained temporarily only as a compatibility bridge during migration, but the steady state should be independent controls.
