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
