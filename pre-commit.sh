#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
cd "$SCRIPT_DIR"

just ci

if [ -n "${PMPROXY_URL:-}" ]; then
    just e2e
else
    echo "  - e2e skipped (set PMPROXY_URL to run, or: just e2e)"
fi

echo "pre-commit passed"
