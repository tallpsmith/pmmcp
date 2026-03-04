#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
cd "$SCRIPT_DIR"

QUIET=false
[[ "${1:-}" == "-q" ]] && QUIET=true

# Prints a progress line, runs the command, then ✓ on success.
# Quiet mode suppresses output unless the command fails.
run_check() {
    local label="$1"; shift
    $QUIET || printf '  → %s...\n' "$label"
    local rc
    if $QUIET; then
        local out
        out=$("$@" 2>&1)
        rc=$?
        [ $rc -ne 0 ] && printf '%s\n' "$out"
    else
        "$@"
        rc=$?
    fi
    [ $rc -ne 0 ] && exit $rc
    $QUIET || printf '  ✓ %s\n' "$label"
}

run_check "sync deps"           uv sync --extra dev
run_check "lint"                uv run ruff check src/ tests/
run_check "format"              uv run ruff format --check src/ tests/
run_check "unit + integration"  uv run pytest -m "not e2e" --cov=pmmcp --cov-fail-under=80 -q

if [ -n "${PMPROXY_URL:-}" ]; then
    run_check "e2e (PMPROXY_URL=$PMPROXY_URL)"  uv run pytest -m e2e -q
else
    $QUIET || printf '  - e2e skipped (set PMPROXY_URL to run)\n'
fi

$QUIET || printf 'pre-commit passed\n'
