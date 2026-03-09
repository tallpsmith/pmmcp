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
  prompts/          # MCP Prompt templates (one module per prompt)
    investigate.py  # investigate_subsystem
    triage.py       # incident_triage
    compare.py      # compare_periods
    health.py       # fleet_health_check
agents/             # Claude Code subagent definitions (.md) — retiring as prompts are implemented
tests/
  unit/             # respx-mocked unit tests per tool
  contract/         # MCP schema + error format contract tests
  integration/      # Live pmproxy tests (skipped without PMPROXY_URL)
  conftest.py
```

## Commands

All dev commands use `uv` — it manages the virtualenv automatically, no activation needed.

> **Multi-environment note**: This project runs on both macOS (local) and Linux (VM). The `.venv` is platform-specific. Always run `uv sync --extra dev` before any test/lint/build commands when there's any chance the environment has changed. `uv sync` is idempotent and fast when nothing changed, but correctly rebuilds the venv for the current platform when needed. Default to running it — do not skip it to save time.

```bash
# Install (dev mode)
uv sync --extra dev

# Test with coverage
uv run pytest --cov=pmmcp --cov-report=term-missing

# Lint
uv run ruff check src/ tests/

# Format
uv run ruff format src/ tests/
```

Coverage gate: ≥80% required (enforced in CI via `--cov-fail-under=80`).

## Key Conventions

- **Never write to stdout** — breaks stdio JSON-RPC framing. Use `logging` (stderr) only.
- **MCP error format**: `{"content": [{"type": "text", "text": "Error: ...\n\nDetails: ...\nSuggestion: ..."}], "isError": True}`
- **Tool injection pattern**: each tool module exposes a `_*_impl(client, ...)` function for testing; the `@mcp.tool` wrapper calls `get_client()`.
- **`interval="auto"`** must be resolved via `resolve_interval()` before any pmproxy call.
- **PMAPI context cache**: lives in `PmproxyClient`; retries on HTTP 403 (expired context).

<!-- MANUAL ADDITIONS START -->
## Container Tooling

**Podman is the preferred container runtime** — not Docker/Docker Desktop. This aligns with the PCP maintainers' tooling preferences.

- Use `podman compose` (or `podman-compose`) instead of `docker compose`
- The compose file is `docker-compose.yml` (filename kept for compatibility); it works with both
- PCP image: `quay.io/performancecopilot/pcp:latest` (hosted on Quay, not Docker Hub)

```bash
# Run E2E services locally
podman compose up -d

# Run E2E tests
PMPROXY_URL=http://localhost:44322 uv run pytest -m e2e

# Tear down
podman compose down
```

## E2E Container Gotchas

- PCP image **requires `privileged: true`** — it uses systemd as PID 1; without it the container exits immediately (code 255)
- Redis host env var is **`KEY_SERVERS: redis-stack:6379`** (NOT `PCP_REDIS_HOST`) — that's what the container entrypoint reads; wrong value causes pmproxy to hang on all series/search calls

## CI / Local E2E Parity — CRITICAL

**The local compose pipeline and the GitHub Actions E2E workflow MUST test the same topology.** When they diverge, tests pass locally but fail in CI (or vice versa) with no obvious cause.

- **Local** uses `docker-compose.yml` which runs the full seeding pipeline: `pmlogsynth-generator` → `pmlogsynth-seeder` → `pcp` + `redis-stack`
- **CI** (`.github/workflows/ci.yml`, `e2e` job) uses GitHub Actions **service containers** — historically just bare `pcp` + `redis-stack` with **no generator or seeder**
- Any E2E test that depends on seeded archive data **will fail in CI** if the workflow doesn't run the seeding pipeline
- **Rule**: when you add or change compose services that affect E2E test data, you MUST update the CI workflow to match. Check both directions — compose → CI and CI → compose.
- **Smell test**: if `podman compose up -d` + `pytest -m e2e` passes locally but CI fails on the same tests, the first thing to check is whether CI runs the same containers

## pmproxy Series API Time Formats

- `/series/values` **rejects abbreviated units** like `-2m`, `-1h` — causes a Content-Length mismatch → `RemoteProtocolError`
- Use full forms: `-2minutes`, `-1hours`, `-7days`
- `_expand_time_units()` in `tools/timeseries.py` handles this expansion; **always call it** before passing `start`/`finish` to `client.series_values()`

## FastMCP List Return Behaviour

- When a tool returns a Python `list`, FastMCP serialises **each element as a separate `TextContent` block** — `result.content` is a list of blocks, not one block containing the whole list
- Correct iteration: `comparisons = [json.loads(c.text) for c in result.content]`
- Wrong: `json.loads(result.content[0].text)` — that gives you the first element only

## pytest-asyncio Session Fixture Teardown

- Need **both** settings in `pyproject.toml` for session-scoped async fixtures to work without cascade timeouts:
  ```toml
  asyncio_default_fixture_loop_scope = "session"
  asyncio_default_test_loop_scope = "session"
  ```
- Wrap session fixture body in `try/except RuntimeError: pass` — anyio cancel-scope teardown fires in a new task and raises a benign RuntimeError

## PMAPI Context Cache

- `PmproxyClient` caches PMAPI contexts; retries on **both HTTP 403 and HTTP 400 "unknown context identifier"** — the 400 case surfaces after container restarts or long idle periods

## Commit Discipline

Commit in small, logical chunks — one concern per commit. Do **not** bundle unrelated changes.

Suggested groupings when implementing tasks:
- Project setup (pyproject.toml, Dockerfile, .gitignore, CI) — one commit
- Each new module + its tests together (e.g. `utils.py` + `test_utils.py`)
- Each tool module + its tests together (e.g. `hosts.py` + `test_hosts.py`)
- Contract/integration tests as their own commit
- Docs (README, CLAUDE.md) as their own commit

Use conventional commit prefixes: `feat:`, `test:`, `chore:`, `fix:`, `docs:`, `refactor:`

## Story-by-Story Development Loop

**Mandatory development pattern** (required by Constitution v1.2.0, Principle II).

Each user story or task is a complete, independent unit of work. The loop:

```
1. Write failing tests  →  uv run pytest (confirm RED)
                       →  git commit "test: <story description>"
2. Implement            →  uv run pytest (confirm GREEN)
3. Refactor             →  uv run pytest (still GREEN)
4. Pre-push sanity      →  scripts/pre-push-sanity.sh (lint + format + tests)
5. Commit + push        →  git commit "feat: <story description>"
                       →  git push
```

Rules:
- No implementation starts before failing tests are committed
- Each story's tests + implementation land as separate commits
- The pre-push sanity check MUST pass before every `git push`
- Stories are worked one at a time — finish and push one before starting the next

## MCP Prompt Pattern

Prompts follow the same `_*_impl()` pattern as tools:

```python
# src/pmmcp/prompts/investigate.py
def _investigate_subsystem_impl(subsystem: str, host: str | None = None, ...) -> list[dict]:
    """Pure function — call directly in unit tests."""
    ...

@mcp.prompt()
def investigate_subsystem(subsystem: str, ...) -> list[dict]:
    return _investigate_subsystem_impl(subsystem, ...)
```

- Prompts return `list[dict]` with `{"role": "user", "content": "..."}` — FastMCP converts to `PromptMessage`
- Registration: side-effect import `import pmmcp.prompts` in `server.py` (bottom, like tools)
- Contract tests use `srv.mcp._prompt_manager.list_prompts()` and `asyncio.run(srv.mcp.get_prompt(...))`

## Pre-Push Sanity Check

**Mandatory before any `git push`** (required by Constitution v1.2.0, Principle II).

Run either:
```bash
scripts/pre-push-sanity.sh
```
or invoke the Claude skill:
```
/pre-push-sanity
```

The check runs in order: lint → format → unit+integration tests (≥80% coverage). E2E tests run only if `PMPROXY_URL` is set; if not set, a warning is printed and E2E is skipped — but this MUST be noted in the PR description.
<!-- MANUAL ADDITIONS END -->

## Active Technologies
- Python 3.11+ + `mcp[cli]` ≥1.26.0 (FastMCP + ClientSession), `anyio` (memory streams), `respx` (already present — mocks httpx for integration tier), `pytest-asyncio` (already present) (002-add-integration-e2e-tests)
- Python 3.8+ (pmlogsynth), Python 3.11 (pmmcp) + pmlogsynth (`git+https://github.com/tallpsmith/pmlogsynth`), (004-pmlogsynth-integration)
- Named volume `pmmcp-archives` (ephemeral; purged on `compose down --volumes`) (004-pmlogsynth-integration)
- Python 3.11+ + `mcp[cli]` >=1.2.0 (FastMCP), `pydantic` v2.x, `httpx` >=0.27 (006-quick-investigate)
- N/A — stateless tool; no persistence (006-quick-investigate)
- Python 3.11+ + `mcp[cli]` ≥1.2.0 (FastMCP), `pydantic` v2.x — no new dependencies (010-specialist-agents)
- N/A — prompts are stateless text generators (010-specialist-agents)

## Recent Changes
- 002-add-integration-e2e-tests: Added Python 3.11+ + `mcp[cli]` ≥1.26.0 (FastMCP + ClientSession), `anyio` (memory streams), `respx` (already present — mocks httpx for integration tier), `pytest-asyncio` (already present)
- 004-pmlogsynth-integration: Compose seeding pipeline live — `pmlogsynth-generator` (one-shot) builds archives from `profiles/*.yml`; `pmlogsynth-seeder` (one-shot) loads them into valkey before `pcp` starts. **`podman compose down --volumes` required for clean teardown** (purges `pmmcp-archives` named volume).
