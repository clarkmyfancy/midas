# ADR 017: Structured Weaviate Memory Artifacts (v2)

- Status: Accepted

## Context

The first Weaviate memory projection stored two artifacts per journal entry:

- a near-raw journal text artifact
- an "episode summary" artifact

In practice, the second artifact was too weak to justify its existence.

- The summary content was mostly a template-wrapped copy of the original journal text.
- Projection naming was ambiguous and overloaded.
- Goals were stored as a JSON string instead of structured metadata.
- Retrieval quality was vulnerable to obvious spelling noise and inconsistent naming because the embedding payload was too close to the raw input.
- The artifact payload did not expose enough typed metadata for downstream filtering or ranking.

This made the Weaviate layer less useful as a durable semantic memory system.

## Decision

Adopt a versioned Weaviate artifact shape for journal-derived memory.

Each journal entry continues to project into two Weaviate artifacts, but with clearer semantics:

- `weaviate_raw_journal_entry`
- `weaviate_semantic_summary`

The raw artifact preserves the original journal text for inspectability.

The semantic artifact stores an actual derived memory summary rather than a template-wrapped copy.

Each Weaviate artifact now includes:

- `projection_version`
- `content_kind`
- `normalized_content`
- structured `goals`
- `goals_text`
- extracted entity metadata such as `people`, `projects`, `contexts`, `moods`
- `canonical_entities`

Embeddings are generated from normalized retrieval text rather than always from the exact raw content.

The schema also distinguishes between retrieval text and structured metadata.

- `content`, `normalized_content`, and `goals_text` are the primary searchable text fields.
- identity and provenance fields such as `user_id`, `source_record_id`, `projection_type`, `projection_version`, and `thread_id` are filter-oriented metadata rather than full-text search content.
- `created_at` is modeled as a true date field.

## Consequences

### Positive

- Retrieval becomes more resilient to obvious spelling mistakes and textual noise.
- The semantic artifact becomes meaningfully different from the raw artifact.
- Projection naming better reflects intent.
- Downstream filtering and ranking can use typed metadata instead of relying only on unstructured text.
- `projection_version` creates a clean path for future artifact migrations.
- Review-style consumers can prefer a single semantic artifact per source record instead of double-counting both raw and derived projections.

### Negative

- Existing Weaviate objects remain in the old shape until reprojected or wiped.
- Schema management becomes more complex because the class may need additive property upgrades.
- Semantic summaries are still heuristic in Core mode and may remain imperfect without stronger extraction or summarization.
- Typed extraction remains quality-sensitive and should drop low-confidence candidates rather than forcing weak guesses into fields like `people` or `projects`.

## Alternatives Considered

- Keep the original artifact format and improve prompt text only: rejected because the structural ambiguity would remain.
- Store only the raw journal text: rejected because retrieval would remain too dependent on literal phrasing.
- Store only a derived summary: rejected because raw inspectability is still useful for debugging and trust.

## Implementation Notes

- The raw artifact remains source-faithful for display, but its embedding input may be normalized.
- The semantic artifact should favor abstraction over paraphrase.
- Typed metadata fields should be conservative. If the pipeline is not confident that a token is a real person or project, it should omit that typed field rather than emitting a misleading value.
- Schema upgrades must be additive so local environments with an existing `MemoryArtifact` class do not require a manual reset before new writes succeed.
- Weaviate remains a rebuildable projection of canonical Postgres records.
