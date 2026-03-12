---
name: midas-publish-guard
description: Enforce Midas pre-push verification. Use when Codex is asked to push a branch to a remote, publish a branch for review, open or update a PR after code changes, or push directly to main. Before any remote push, run `.codex/skills/midas-publish-guard/scripts/run_publish_checks.sh` from the repo root and stop if it fails.
---

# Midas Publish Guard

## Required Workflow

1. Treat any request mentioning push, publish branch, send to origin, update PR, merge prep, or push to `main` as a guarded publish task.
2. Before any remote push, run:

```bash
sh .codex/skills/midas-publish-guard/scripts/run_publish_checks.sh
```

3. Run the script from the repository root. It resolves the repo root and executes the current automated test suite.
4. Do not push if the script exits non-zero or if the suite cannot be run.
5. Re-run the script if code changes after the last passing run and before the push step.
6. If the user explicitly asks to skip tests, refuse the push step and explain that this workspace requires the publish checks first.

## Current Suite Definition

- The current automated test entrypoint is `pnpm test` from the repository root.
- Today that command reaches `apps/backend/package.json`, which runs `uv run pytest`.
- The existing test files are:
  - `apps/backend/tests/test_api.py`
  - `apps/backend/tests/test_graph.py`
  - `apps/backend/tests/test_loader.py`
- `apps/web` and `apps/ios` do not currently define automated `test` scripts. Do not invent test commands for them.
- If the repository adds more real test commands later, update this skill and its script before relying on them.

## Extra Validation

- If the change touches generated contracts or the web app, optionally run `pnpm generate:types`, `pnpm --filter @midas/web typecheck`, and `pnpm --filter @midas/web build` after the required test pass.
- If the change touches iOS build files, optionally run `xcodegen generate` plus the documented `xcodebuild` simulator build. Treat those as broader release validation, not as substitutes for the required automated tests.

## Failure Handling

- Surface the exact failing command and stop.
- Treat missing dependencies or interpreter mismatches as hard blockers.
- Do not report a branch as ready to publish unless the latest run passed against the current tree.

## Resource

- Use `scripts/run_publish_checks.sh` instead of retyping the commands.
