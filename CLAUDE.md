# pmmcp Development Guidelines

## Stack

Python 3.11+ with:
- `mcp[cli]` ≥1.2.0 (FastMCP) — MCP server framework
- `pydantic` v2.x + `pydantic-settings` — data models and config
- `httpx` ≥0.27 — async HTTP client for pmproxy REST API
- `hatchling` — build backend

Dev tools: `pytest`, `pytest-asyncio`, `respx`, `ruff`, `pytest-cov`

## Project Structure

```text
src/pmmcp/          # Main package
  __init__.py       # __version__ = "0.1.0"
  __main__.py       # CLI entrypoint (argparse → mcp.run)
  config.py         # PmproxyConfig(BaseSettings)
  models.py         # Pydantic v2 models
  utils.py          # resolve_interval(), parse_time_expr()
  client.py         # PmproxyClient (httpx async)
  server.py         # FastMCP instance + lifespan
  tools/            # One module per tool group
    hosts.py        # pcp_get_hosts
    live.py         # pcp_fetch_live
    timeseries.py   # pcp_fetch_timeseries, pcp_query_series
    search.py       # pcp_search
    derived.py      # pcp_derive_metric
    discovery.py    # pcp_discover_metrics, pcp_get_metric_info
    comparison.py   # pcp_compare_windows
agents/             # Claude Code subagent definitions (.md)
tests/
  unit/             # respx-mocked unit tests per tool
  contract/         # MCP schema + error format contract tests
  integration/      # Live pmproxy tests (skipped without PMPROXY_URL)
  conftest.py
```

## Commands

```bash
# Install (dev mode)
pip install -e ".[dev]"

# Test with coverage
pytest --cov=pmmcp --cov-report=term-missing

# Lint
ruff check src/ tests/

# Format
ruff format src/ tests/
```

Coverage gate: ≥80% required (enforced in CI via `--cov-fail-under=80`).

## Key Conventions

- **Never write to stdout** — breaks stdio JSON-RPC framing. Use `logging` (stderr) only.
- **MCP error format**: `{"content": [{"type": "text", "text": "Error: ...\n\nDetails: ...\nSuggestion: ..."}], "isError": True}`
- **Tool injection pattern**: each tool module exposes a `_*_impl(client, ...)` function for testing; the `@mcp.tool` wrapper calls `get_client()`.
- **`interval="auto"`** must be resolved via `resolve_interval()` before any pmproxy call.
- **PMAPI context cache**: lives in `PmproxyClient`; retries on HTTP 403 (expired context).

<!-- MANUAL ADDITIONS START -->
## Linting — MANDATORY AFTER EVERY CODE CHANGE

**BLOCKING REQUIREMENT: After any edit to `src/` or `tests/`, you MUST run:**

```bash
.venv/bin/ruff check src/ tests/
```

The venv is not on `$PATH` in Claude Code sessions — always invoke via `.venv/bin/ruff`.
Fix all reported violations before committing. No exceptions: CI will catch it and the
embarrassment just isn't worth it.

## Commit Discipline

Commit in small, logical chunks — one concern per commit. Do **not** bundle unrelated changes.

Suggested groupings when implementing tasks:
- Project setup (pyproject.toml, Dockerfile, .gitignore, CI) — one commit
- Each new module + its tests together (e.g. `utils.py` + `test_utils.py`)
- Each tool module + its tests together (e.g. `hosts.py` + `test_hosts.py`)
- Contract/integration tests as their own commit
- Docs (README, CLAUDE.md) as their own commit

Use conventional commit prefixes: `feat:`, `test:`, `chore:`, `fix:`, `docs:`, `refactor:`
<!-- MANUAL ADDITIONS END -->
