set shell := ["bash", "-c"]

# List available recipes
default:
    @just --list

# Sync dev dependencies
sync:
    uv sync --extra dev

# Run linter
lint:
    uv run ruff check src/ tests/

# Check formatting (non-destructive)
format:
    uv run ruff format --check src/ tests/

# Auto-fix lint and format issues
fix:
    uv run ruff check --fix src/ tests/
    uv run ruff format src/ tests/

# All static quality checks (lint + format)
check: lint format

# Run unit + integration tests with coverage gate
test:
    uv run python -m pytest -m "not e2e" --cov=pmmcp --cov-fail-under=80 -q

# Full local quality gate (check + test)
ci: check test

# Start services and run E2E tests (requires podman)
# Uses --wait to match CI behaviour — all containers must be healthy before tests run
e2e:
    PROFILES_DIR=./profiles/e2e podman compose up -d --wait --wait-timeout 120
    PMPROXY_URL=http://localhost:44322 GRAFANA_URL=http://localhost:3000 MCP_GRAFANA_URL=http://localhost:8000 uv run python -m pytest -m e2e -q
    @echo "Stack still running — run 'podman compose down --volumes' to purge seeded data before next run"

# Brings up the full stack, seeded (not e2e)
doit:
   podman compose up -d --wait --wait-timeout 120

# Removes all containers and their volumes for a clean state
teardown:
    podman compose down --volumes