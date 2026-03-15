# ADR 019: Core Storage, Pro Analytics Tier Boundary

- Status: Accepted

## Context

Midas previously mixed product tiers in a way that was hard to explain and hard to enforce:

- weekly review was treated as a premium capability even though it is a normal baseline expectation
- the review endpoint bundled together standard reflection data and heavier graph/vector analysis
- capability names like `pro_analytics` did not clearly describe what was actually premium

The intended product model is simpler:

- Core should include the standard journaling, reflection, clarification, and storage experience
- Pro should unlock deeper analytics over the same stored data

## Decision

Define the tier boundary around analytics depth, not storage or ingestion.

Core includes:

- the same auth/session model
- the same journal and reflection writes
- the same memory and storage pipeline
- clarifications
- weekly reflection and weekly review

Pro includes:

- advanced longitudinal analytics across stored data
- graph-driven interpretation
- heavier pattern mining and premium insights

The capability model should reflect that split:

- `weekly_reflection` is a Core capability
- `advanced_analytics` is the premium capability exposed to clients

## Consequences

### Positive

- The pricing story is easier to explain because all users keep the same capture and storage model.
- Core users still get a complete reflection product instead of a crippled shell.
- Premium value is concentrated in deeper interpretation rather than basic expected behavior.

### Negative

- Review and insights can no longer share the same mixed payload shape.
- Client surfaces must be explicit about which screens are standard reflection versus premium analytics.
- Some existing internal implementations may still need follow-up refactors if they implicitly assume premium reasoning outside the analytics layer.

## Implementation Notes

- `/review` should remain a Core weekly reflection surface.
- `/insights` should remain the Pro analytics surface.
- Graph and vector analytics should not be required to produce the standard weekly review.
- Storage writes, retention, and ingestion should not diverge between Core and Pro tiers.
