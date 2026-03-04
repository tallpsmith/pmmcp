# Design: just task runner for pmmcp dev workflow

**Date**: 2026-03-04
**Branch**: 006-just-task-runner (proposed)
**Status**: Approved

## Problem

`pre-commit.sh` and `scripts/pre-push-sanity.sh` contain raw `uv run` commands
duplicated across both files. There is no single authoritative place to find
"how do I run lint locally?". CI duplicates the same commands a third time.
The `pytest` shebang portability issue (hardcoded path from original dev machine)
further complicates using `uv run pytest` directly.

## Decision

Use **`just`** as the project task runner. `just` is a language-agnostic command
runner (Justfile at repo root) and the idiomatic choice for uv-based Python
projects in 2025. Individual recipes call `uv run` internally.

`pre-commit.sh` and `scripts/pre-push-sanity.sh` are rewritten to delegate to
`just ci`, becoming thin wrappers. CONTRIBUTING.md is updated to document `just`
as a dev prerequisite and the primary interface.

## Justfile Recipes

| Recipe | Command | Purpose |
|--------|---------|---------|
| `just sync` | `uv sync --extra dev` | Sync dev dependencies |
| `just lint` | `ruff check src/ tests/` | Run linter |
| `just format` | `ruff format --check src/ tests/` | Check formatting |
| `just fix` | ruff fix + format | Auto-fix lint and format |
| `just check` | lint + format | All static quality checks |
| `just test` | pytest not e2e, coverage ≥80% | Unit + integration |
| `just e2e` | podman compose up + pytest e2e | Full stack E2E |
| `just ci` | check + test | Full local quality gate |

`just` (no args) lists available recipes.

## File Changes

| File | Change |
|------|--------|
| `Justfile` | **NEW** — all recipes |
| `pre-commit.sh` | **REWRITE** — delegates to `just ci` + optional `just e2e` |
| `scripts/pre-push-sanity.sh` | **REWRITE** — delegates to `just ci` + optional `just e2e` |
| `CONTRIBUTING.md` | **UPDATE** — document `just` prerequisite and recipes |

CI (`.github/workflows/ci.yml`) is left unchanged — it uses direct `uv run`
commands, which is appropriate for CI where `just` may not be installed.
Updating CI to use `just` is a follow-up concern.

## Prerequisites

`just` is installed via the system package manager, not via pip:

```bash
brew install just          # macOS
apt install just           # Debian/Ubuntu
cargo install just         # anywhere with Rust
```

## e2e Recipe Detail

The `just e2e` recipe:
1. Calls `podman compose up -d` (uses existing `docker-compose.yml`)
2. Waits for pmproxy to be ready at `http://localhost:44322`
3. Sets `PMPROXY_URL` and runs `pytest -m e2e`

`just ci` does **not** include e2e — matches current pre-commit behaviour.
E2E requires explicit `just e2e` invocation.

## Quiet Mode

Current `pre-commit.sh` has a `-q` flag. Since `just` recipes produce clean
output by default, the quiet mode wrapper is dropped. Failures still print
full output (just's default behaviour).
