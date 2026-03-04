# just Task Runner Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace scattered `uv run` commands across `pre-commit.sh` and `scripts/pre-push-sanity.sh` with a `Justfile` that provides `just lint`, `just test`, `just e2e`, `just ci` as the single authoritative dev interface.

**Architecture:** A `Justfile` at repo root defines all dev recipes; each calls `uv run` internally. Both shell scripts become thin 10-line wrappers that call `just ci`. CONTRIBUTING.md is rewritten to document `just` as the primary dev interface.

**Tech Stack:** `just` (system binary — `brew install just`), `uv run python -m pytest` (not `uv run pytest` — avoids venv shebang portability issue), `ruff`, `podman compose`

---

### Task 1: Scaffold Justfile with quality check recipes

**Files:**
- Create: `Justfile`

**Step 1: Verify `just` is installed**

```bash
just --version
```

Expected: `just 1.x.x`. If missing: `brew install just` (macOS) or `apt install just` / `cargo install just`.

**Step 2: Create `Justfile` at repo root**

```just
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
```

`set shell := ["bash", "-c"]` ensures bash is used for all recipes — needed for the e2e wait loop in Task 3.

**Step 3: Verify each recipe**

```bash
just --list
just sync
just lint
just format
just check
```

Expected: each exits 0, output identical to the equivalent `uv run` commands.

**Step 4: Commit**

```bash
git add Justfile
git commit -m "chore: add Justfile with lint, format, check, fix recipes"
```

---

### Task 2: Add test and ci recipes

**Files:**
- Modify: `Justfile`

**Step 1: Verify the test command works standalone**

```bash
uv run python -m pytest -m "not e2e" --cov=pmmcp --cov-fail-under=80 -q
```

Expected: all tests pass, coverage ≥80%.

> **Why `python -m pytest` not `uv run pytest`?** The venv's `pytest` script has a hardcoded shebang (`#!/Users/psmith/dev/...`) from the machine it was built on. `python -m pytest` bypasses the shebang entirely and works everywhere.

**Step 2: Append to `Justfile`**

```just
# Run unit + integration tests with coverage gate
test:
    uv run python -m pytest -m "not e2e" --cov=pmmcp --cov-fail-under=80 -q

# Full local quality gate (check + test)
ci: check test
```

**Step 3: Verify**

```bash
just test
just ci
```

Expected: both exit 0.

**Step 4: Commit**

```bash
git add Justfile
git commit -m "chore: add test and ci recipes to Justfile"
```

---

### Task 3: Add e2e recipe

**Files:**
- Modify: `Justfile`

**Step 1: Append to `Justfile`**

```just
# Start services and run E2E tests (requires podman)
e2e:
    PROFILES_DIR=./profiles/e2e podman compose up -d
    @echo "Waiting for pmproxy at http://localhost:44322..."
    @for i in $(seq 1 30); do \
        curl -sf http://localhost:44322/pmapi/context?hostspec=localhost && break; \
        sleep 2; \
    done
    PMPROXY_URL=http://localhost:44322 uv run python -m pytest -m e2e -q
```

**Step 2: Verify syntax (dry run — no podman required)**

```bash
just --dry-run e2e
```

Expected: prints the commands without executing them. No errors.

**Step 3: Commit**

```bash
git add Justfile
git commit -m "chore: add e2e recipe to Justfile"
```

---

### Task 4: Rewrite pre-commit.sh to delegate to just

**Files:**
- Modify: `pre-commit.sh`

**Step 1: Read the current file** (already in context — `pre-commit.sh` at repo root)

Note what's being dropped: the `-q` quiet mode flag and `run_check` helper. `just` recipes produce clean output by default; the complexity isn't needed.

**Step 2: Rewrite `pre-commit.sh`**

```bash
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
```

**Step 3: Verify**

```bash
./pre-commit.sh
```

Expected: exits 0, output matches `just ci`.

**Step 4: Commit**

```bash
git add pre-commit.sh
git commit -m "chore: pre-commit.sh delegates to just ci"
```

---

### Task 5: Rewrite scripts/pre-push-sanity.sh to delegate to just

**Files:**
- Modify: `scripts/pre-push-sanity.sh`

**Step 1: Rewrite `scripts/pre-push-sanity.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
cd "$SCRIPT_DIR"

just ci

if [ -n "${PMPROXY_URL:-}" ]; then
    just e2e
else
    echo "⚠️  PMPROXY_URL not set — E2E skipped (start containers and set PMPROXY_URL to run)"
fi

echo "✅ Pre-push sanity passed"
```

**Step 2: Verify**

```bash
scripts/pre-push-sanity.sh
```

Expected: exits 0.

**Step 3: Commit**

```bash
git add scripts/pre-push-sanity.sh
git commit -m "chore: pre-push-sanity.sh delegates to just ci"
```

---

### Task 6: Update CONTRIBUTING.md

**Files:**
- Modify: `CONTRIBUTING.md`

**Step 1: Rewrite `CONTRIBUTING.md`**

```markdown
# Contributing

## Dev setup

```bash
git clone <repository-url>
cd pmmcp
brew install just          # macOS — or: apt install just / cargo install just
uv sync --extra dev
```

## Daily dev commands

```bash
just lint       # run linter
just format     # check formatting
just fix        # auto-fix lint + format issues
just check      # lint + format (static quality gate)
just test       # unit + integration tests (coverage ≥80%)
just e2e        # spin up podman stack and run E2E tests
just ci         # full local quality gate (check + test)
```

`just` with no arguments lists all available recipes.

## Local quality gate

Before pushing, run the quality gate — it mirrors CI exactly:

```bash
just ci
```

To include E2E tests:

```bash
just e2e
```

## Test structure

| Directory | Marker | Purpose |
|-----------|--------|---------|
| `tests/unit/` | `not e2e` | respx-mocked unit tests per tool |
| `tests/integration/` | `not e2e` | MCP schema and error format contract tests |
| `tests/e2e/` | `e2e` | Full stack against seeded pmproxy; requires `PMPROXY_URL` |

TDD is mandatory: write failing tests before implementation. Never delete existing
tests — discuss failures before removing anything.

## PR conventions

- One logical change per PR; commit in small, focused chunks
- `feat:`, `fix:`, `test:`, `docs:`, `chore:`, `refactor:` prefixes on commit messages
- Focus commit messages on *why*, not *what*
- Run `just ci` and confirm it exits 0 before opening a PR
```

**Step 2: Commit**

```bash
git add CONTRIBUTING.md
git commit -m "docs: update CONTRIBUTING.md for just task runner"
```

---

### Task 7: Final verification and push

**Step 1: Confirm full recipe listing**

```bash
just --list
```

Expected:
```
Available recipes:
    check   # All static quality checks (lint + format)
    ci      # Full local quality gate (check + test)
    default # List available recipes
    e2e     # Start services and run E2E tests (requires podman)
    fix     # Auto-fix lint and format issues
    format  # Check formatting (non-destructive)
    lint    # Run linter
    sync    # Sync dev dependencies
    test    # Run unit + integration tests with coverage gate
```

**Step 2: Run the full pipeline**

```bash
just ci
```

Expected: exits 0, all tests pass, coverage ≥80%.

**Step 3: Push**

```bash
git push
```
