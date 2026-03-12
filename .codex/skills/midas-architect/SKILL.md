---
name: midas-architect
description: Protect the Midas open-core boundary. Use when adding or modifying agents, capabilities, entitlements, premium feature gates, or any backend code that might blur Core versus Pro ownership. Classify the work as Core or Pro first, keep interfaces public under `apps/backend/midas/interfaces`, keep Core fallbacks under `apps/backend/midas/core`, and never import `midas_pro` outside the guarded loader path.
---

# Midas Architect

## Classification

1. Classify the feature before writing code.
2. Mark it as Core if the public repo must remain fully runnable without proprietary models, secrets, or premium reasoning.
3. Mark it as Pro if it depends on premium analytics, higher-reasoning orchestration, hosted-only infrastructure, or private `midas_pro` implementations.
4. If the user asks for a blended feature, split it into a public interface plus a Core fallback and a Pro implementation.

## Required Boundary Rules

1. Define extension contracts in `apps/backend/midas/interfaces`. For agent features, start with `apps/backend/midas/interfaces/agents.py`.
2. Place the public fallback in `apps/backend/midas/core`. If the fallback grows beyond the loader, create a dedicated module there instead of pushing logic into app code.
3. Resolve implementations through `CapabilityRegistry` and `load_capabilities()`. Consume them with `registry.resolve(...)`.
4. Never import `midas_pro` directly from `app/`, `packages/`, `apps/web`, or `apps/ios`.
5. Keep the only direct `midas_pro` import behind the guarded loader boundary in `apps/backend/midas/core/loader.py` unless the architecture is intentionally redesigned.
6. When capability names change, update the registry, entitlement checks, API payloads, client gates, and tests in the same change.

## Agent Rule

- If a feature needs high-reasoning analytics, define an interface under `midas.interfaces.agents`, provide a Core fallback under `midas.core`, and register both through the capability loader.
- Never hard-code a `midas_pro` class into the public graph.

## Review Checklist

- Ask: can this code run in Core mode with `midas_pro` absent?
- Ask: is the capability visible through the registry instead of a direct import?
- Ask: does the public repo expose only stable interfaces and fallbacks?
- Ask: do tests still cover the missing-Pro path?

## Resource

- Load `references/open-core-boundary.md` for the current file map, anti-patterns, and a concrete change checklist.
