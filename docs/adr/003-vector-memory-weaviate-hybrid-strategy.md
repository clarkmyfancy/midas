# ADR 003: Vector Memory via Weaviate (Hybrid Strategy)

- Status: Accepted

## Context

Midas needs to store long-term neural memory such as journals while supporting zero-downtime migrations between embedding models.

## Decision

Use Weaviate for the vector database.

## Consequences

### Positive

- Weaviate supports collection aliases, which enables blue-green style migrations when upgrading from `text-embedding-3-small` to a stronger embedding model.
- The model migration story aligns with a system that expects long-lived memory rather than disposable retrieval state.

### Negative

- Self-hosting Weaviate requires more DevOps expertise than managed alternatives like Pinecone.

## Alternatives Considered

- Pinecone: Simpler to operate, but introduces a more proprietary dependency and stronger vendor lock-in.
- Milvus: Strong at scale, but typically comes with more operational complexity and heavier Kubernetes expectations.

