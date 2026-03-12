#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../../../.." && pwd)

cd "$REPO_ROOT"

echo "[midas-publish-guard] Running automated tests from $REPO_ROOT"
echo "[midas-publish-guard] Command: pnpm test"
pnpm test
