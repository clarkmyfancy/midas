# Open-Core Boundary

## Current Boundary Files

- `apps/backend/midas/interfaces/agents.py`: public agent interfaces
- `apps/backend/midas/core/registry.py`: capability and implementation registry
- `apps/backend/midas/core/loader.py`: guarded `midas_pro` import plus Core fallback registration
- `apps/backend/midas/core/entitlements.py`: runtime entitlement checks
- `apps/backend/tests/test_loader.py`: missing-Pro regression coverage
- `apps/backend/tests/test_api.py`: capability endpoint and guarded route coverage

## Safe Pattern

1. Add or extend a public interface in `apps/backend/midas/interfaces`.
2. Implement a Core fallback in `apps/backend/midas/core`.
3. Register the fallback and capability flags in `apps/backend/midas/core/loader.py`.
4. Let the loader replace the fallback with a Pro implementation only when `midas_pro` is importable.
5. Consume the interface through `CapabilityRegistry`, not through a direct class import.

## Anti-Patterns

- Importing `midas_pro` anywhere outside the guarded loader path
- Importing a concrete Pro agent into `app/agents/graph.py`
- Using boolean feature flags in app code without going through the registry
- Returning a Pro-only payload shape from a public Core endpoint
- Adding a premium feature to web or iOS without wiring the capability map first

## Change Checklist

- Add or update the interface
- Add or update the Core fallback
- Register the capability and default flags
- Update the consuming graph or route to resolve through the registry
- Update API, entitlement, and loader tests
- Update web or iOS gates if the capability is user-visible
