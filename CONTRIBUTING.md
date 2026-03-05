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
