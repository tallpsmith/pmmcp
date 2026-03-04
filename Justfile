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
e2e:
    PROFILES_DIR=./profiles/e2e podman compose up -d
    @echo "Waiting for pmproxy at http://localhost:44322..."
    @for i in $(seq 1 30); do \
        curl -sf http://localhost:44322/pmapi/context?hostspec=localhost && break; \
        sleep 2; \
    done
    PMPROXY_URL=http://localhost:44322 uv run python -m pytest -m e2e -q
    @echo "Stack still running — run 'podman compose down --volumes' to purge seeded data before next run"
