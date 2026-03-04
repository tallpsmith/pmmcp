# Contributing

## Dev setup

```bash
git clone <repository-url>
cd pmmcp
uv sync --extra dev
```

## Local quality gate

Before pushing, run the pre-commit gate — it mirrors CI exactly:

```bash
./pre-commit.sh
```

Runs in order: dependency sync, lint, format check, unit + integration tests (≥80%
coverage), and E2E tests if `PMPROXY_URL` is set.

To run E2E tests against the local compose stack:

```bash
PROFILES_DIR=./profiles/e2e podman compose up -d
PMPROXY_URL=http://localhost:44322 ./pre-commit.sh
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
- `feat:`, `fix:`, `test:`, `docs:`, `refactor:` prefixes on commit messages
- Focus commit messages on *why*, not *what*
- Run `./pre-commit.sh` and confirm it exits 0 before opening a PR
