# ADR 009: Runtime Entitlement Verification (Cloud-Verified)

- Status: Accepted

## Context

Midas needs a professional way to verify subscription status at runtime that is difficult to bypass and integrates with the revenue stack.

## Decision

Integrate with the Polar.sh API for real-time entitlement checks. The backend will cache Pro status per user session and gate specific agent nodes or API routes accordingly.

## Consequences

### Positive

- Provides a strong security boundary for feature gating.
- Allows instant feature enablement after a user pays.
- Creates a SaaS-native upgrade experience instead of a manual unlock flow.

### Negative

- Introduces a runtime dependency on an external API, which requires robust error handling and fallback behavior to Core mode.

