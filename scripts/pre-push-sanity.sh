#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
cd "$SCRIPT_DIR/.."

just ci

if [ -n "${PMPROXY_URL:-}" ]; then
    just e2e
else
    echo "⚠️  PMPROXY_URL not set — E2E skipped (start containers and set PMPROXY_URL to run)"
fi

echo "✅ Pre-push sanity passed"
