# ADR 016: Hybrid Memory via Postgres, Weaviate, and Neo4j

- Status: Accepted

## Context

Midas needs a memory architecture that can do three things at once:

1. Preserve raw user data with fast, atomic, reliable writes.
2. Retrieve semantically relevant past reflections without relying on exact keyword matches.
3. Explain recurring behavioral loops, conflicts, and patterns in a way that is inspectable by both the system and the user.

No single storage system satisfies all three constraints well.

- Postgres is the strongest source of truth for transactional writes, user isolation, deletes, and auditability.
- Weaviate is the strongest fit for vector retrieval over journals, summaries, and other unstructured memory.
- A dedicated graph database is the strongest fit for storing explicit relationships between people, places, contexts, moods, habits, goals, projects, and other recurring entities extracted from journals and events.

The system must also preserve privacy boundaries.

- Raw user data must remain strongly linked to a single user identity across all stores.
- Derived memories must be deletable by provenance, starting from the canonical record in Postgres.
- Sensitive content should support application-layer encryption that can be disabled in early development and testing.

Finally, the graph layer is intentionally probabilistic rather than user-authored in v1.

- The graph is derived from journals and events.
- The system should emit confidence scores and source links for extracted nodes and edges.
- The system should attempt entity resolution across variants such as `Joshua`, `joshua`, `Josh`, or `josh`.
- When confidence is below a configured threshold, the system should ask the user to clarify rather than silently merge or split entities.

## Decision

Adopt a hybrid memory architecture:

- Postgres is the canonical system of record.
- Weaviate stores derived vector memories.
- Neo4j stores derived knowledge graph facts.

This decision prioritizes explainability without sacrificing ingestion reliability.

### Postgres responsibilities

- Store raw journal entries, health snapshots, auth data, reflection sessions, import jobs, and synchronization metadata.
- Issue canonical primary keys for all user-owned records.
- Act as the only storage dependency required for a successful ingestion write.
- Record projection status for downstream Weaviate and Neo4j materialization.
- Drive cascaded deletes into derived memory systems.

### Weaviate responsibilities

- Store vectorized journal chunks.
- Store reflection summaries.
- Store health-context summaries.
- Store episode summaries and other semantically retrievable memory artifacts.
- Retrieve relevant prior memories for weekly reflections, pattern analysis, and agent context assembly.

### Neo4j responsibilities

- Store extracted entities and relationships with provenance and confidence.
- Model people, places, contexts, moods, projects, habits, goals, and other recurring concepts.
- Model relationships such as `affected`, `supported`, `conflicts_with`, `led_up_to`, `triggered_by`, `precedes`, `causes`, `recurs`, `about`, `contributed_to`, and `experienced`.
- Support explainable pattern detection and user-facing reasoning such as recurring loops, identity conflicts, and environmental triggers.

## Architecture

### Ingestion path

The ingestion write path must remain simple and durable.

1. Accept a journal entry or event payload.
2. Write the canonical record to Postgres in a single transaction.
3. Persist a projection job or outbox event in the same transaction.
4. A background worker derives vector memories for Weaviate.
5. A background worker derives graph nodes and edges for Neo4j.

Only the Postgres transaction is required for the request to succeed.

If Weaviate or Neo4j is slow, unavailable, or undergoing migration, ingestion still succeeds because the derived projections can be replayed from Postgres later.

### Read path

Different product surfaces will consult different combinations of storage systems.

- Timeline and edit views read from Postgres.
- Weekly reflections read recent source-of-truth events from Postgres and relevant semantic memories from Weaviate.
- Pattern detection and explainability views read graph neighborhoods from Neo4j and can link each conclusion back to source records in Postgres.
- Higher-level agent memory can combine all three:
  - Postgres for recent factual state
  - Weaviate for fuzzy semantic recall
  - Neo4j for explicit structured patterns

### Entity resolution

Neo4j facts are derived and probabilistic, not silently authoritative.

- Each node and edge must retain source links back to Postgres records.
- Each extraction must retain a confidence score.
- Entity resolution must support aliases and canonicalization for cases such as `Joshua`, `joshua`, `Josh`, and `josh`.
- When merge confidence is below threshold, the system should create a clarification task instead of merging automatically.

### Deletion and privacy

Deletes flow from the source of truth outward.

1. Delete or tombstone the canonical Postgres record.
2. Resolve all derived Weaviate objects and Neo4j nodes and edges by source provenance.
3. Remove or tombstone derived artifacts.
4. Recompute any aggregate summaries affected by that deletion.

Every derived artifact must include both:

- `user_id`
- `source_record_id`

This prevents cross-user leakage and gives the system an unambiguous deletion path.

### Encryption

Sensitive content should support application-layer encryption at rest across all three stores.

- Postgres should support encrypted journal text and other sensitive fields.
- Weaviate should support encrypted payload text or encrypted redacted payload variants when feasible.
- Neo4j should avoid storing more raw text than necessary and should encrypt sensitive node properties where stored.

This encryption should be controlled by an environment toggle in early development so testing, fixtures, and debugging remain practical while the encryption path is being validated.

The long-term default should be encryption enabled.

## Consequences

### Positive

- Preserves a fast, atomic, reliable source of truth.
- Keeps vector retrieval and graph reasoning out of the critical write path.
- Improves explainability because the system can cite both semantic memories and explicit relationship paths.
- Supports richer user understanding than Postgres-only or vector-only designs.
- Makes deletion and replay operationally tractable because all derived state flows from canonical source records.
- Allows independent evolution of semantic memory and graph extraction logic without rewriting the source-of-truth model.

### Negative

- Operational complexity increases because the system now owns three storage layers instead of one.
- Projection failures, replay logic, and consistency monitoring become first-class concerns.
- Entity extraction and resolution can introduce noisy or incorrect graph facts if thresholds are poorly tuned.
- Encryption across three systems adds implementation and debugging complexity.

## Alternatives Considered

- Postgres only: strongest operational simplicity, but too weak for semantic memory and explainable relational reasoning.
- Postgres plus Weaviate only: strong retrieval, but recurring patterns remain implicit and must be repeatedly re-inferred by the model.
- Postgres plus Neo4j only: strong explainability, but weak semantic recall over raw journal language.
- Weaviate only: useful for retrieval, but not a sufficient source of truth and too weak for durable relationship modeling.
- Neo4j only: useful for explicit patterns, but too lossy for raw journaling nuance and semantic recall.

## Implementation Notes

- Keep Postgres writes synchronous and derived projections asynchronous.
- Treat Weaviate and Neo4j as rebuildable projections from canonical Postgres records.
- Keep graph extraction and entity resolution in the public Core architecture, with room for stronger proprietary extraction or reasoning in `midas_pro` later through existing interface boundaries.
- Prefer storing graph provenance and confidence explicitly rather than hiding them inside prompts or transient traces.
