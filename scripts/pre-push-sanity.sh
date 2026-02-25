#!/usr/bin/env bash
set -euo pipefail

echo "=== Lint ==="
uv run ruff check src/ tests/

echo "=== Format ==="
uv run ruff format --check src/ tests/

echo "=== Unit + Integration ==="
uv run pytest -m "not e2e" --cov=pmmcp --cov-fail-under=80 -q

if [ -n "${PMPROXY_URL:-}" ]; then
  echo "=== E2E (PMPROXY_URL=$PMPROXY_URL) ==="
  uv run pytest -m e2e -q
else
  echo "⚠️  PMPROXY_URL not set — E2E skipped (start containers and set PMPROXY_URL to run)"
fi

echo "✅ Pre-push sanity passed"
