# Implementation Plan: Integration and E2E Test Suites

**Branch**: `002-add-integration-e2e-tests` | **Date**: 2026-02-25 | **Spec**: `specs/002-add-integration-e2e-tests/spec.md`

---

## Summary

Add two new test tiers to the pmmcp test pyramid: (1) **integration tests** that exercise all nine MCP tools through the real MCP protocol dispatch path using in-process memory streams and respx-mocked httpx, and (2) **E2E tests** that launch pmmcp as a real subprocess over stdio and verify full-stack behaviour against a containerised PCP + redis-stack instance. GitHub Actions CI is extended with a second job providing PCP service containers so E2E runs on every PR.

---

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: `mcp[cli]` ≥1.26.0 (FastMCP + ClientSession), `anyio` (memory streams), `respx` (already present — mocks httpx for integration tier), `pytest-asyncio` (already present)
**New Dev Dependencies**: none — `respx` already covers the mock HTTP layer; `mcp.client.stdio` is part of the installed `mcp` package
**Storage**: N/A
**Testing**: `pytest`, `pytest-asyncio`, `respx`, `pytest-cov` (all existing)
**Target Platform**: Linux CI (ubuntu-latest), macOS developer machines
**Performance Goals**: Integration suite ≤60s total (SC-002); E2E suite ≤5min per tool (SC-003)
**Constraints**: No new runtime dependencies; no new dev dependencies needed; ≥80% coverage gate must be maintained (SC-005)
**Scale/Scope**: 9 tools × 2 test tiers + CI workflow update

---

## Constitution Check

| Principle | Status | Notes / Justification |
|-----------|--------|----------------------|
| I. Code Quality — linting enforced, single-responsibility, complexity ≤ 10 | PASS | All new code linted via `ruff`. Test files follow single-responsibility: one file per tool group. Fixture complexity ≤ 10. |
| II. Testing Standards — TDD cycle, ≥80% unit coverage, contract tests | PASS | TDD enforced throughout (FR-012). Coverage gate maintained (FR-010, SC-005). Integration tests are the new contracts for the MCP protocol layer. |
| III. UX Consistency — design system adherence, WCAG, actionable errors | N/A | No user-facing surfaces. E2E diagnostic messages follow the existing MCP error format convention. |
| IV. Performance — latency SLA defined, perf budget in CI | PASS | SC-002: integration suite ≤60s enforced by session-scoped server fixture. SC-003: E2E per-tool SLAs already defined in existing integration tests. |
| V. Simplicity — YAGNI, no speculative abstractions | PASS | No new abstractions beyond the two fixtures. No pytest plugins invented. respx continues to handle HTTP mocking — no new dep introduced. |

---

## Project Structure

### Documentation (this feature)

```text
specs/002-add-integration-e2e-tests/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── data-model.md        ← Phase 1 output
└── tasks.md             ← Phase 2 output (/speckit.tasks — not yet created)
```

### Source Code Changes

```text
tests/
├── conftest.py                         # existing — minor additions for markers
├── unit/                               # existing — unchanged
├── contract/                           # existing — unchanged
├── integration/
│   ├── __init__.py                     # existing (empty) — keep
│   ├── conftest.py                     # NEW: session-scoped MCP server fixture
│   └── test_integration.py            # REPLACE: rename old file → tests/e2e/test_live.py
│       test_hosts.py                   # NEW: pcp_get_hosts integration
│       test_live.py                    # NEW: pcp_fetch_live integration
│       test_timeseries.py              # NEW: pcp_fetch_timeseries + pcp_query_series
│       test_search.py                  # NEW: pcp_search integration
│       test_discovery.py              # NEW: pcp_discover_metrics + pcp_get_metric_info
│       test_derived.py                # NEW: pcp_derive_metric integration
│       test_comparison.py             # NEW: pcp_compare_windows integration
└── e2e/
    ├── __init__.py                     # NEW
    ├── conftest.py                     # NEW: E2E gating + subprocess harness
    ├── test_live.py                    # RELOCATED from tests/integration/test_integration.py
    └── test_tools.py                   # NEW: E2E tool coverage (all 9 tools)

docker-compose.yml                      # NEW: pcp + redis-stack
.github/workflows/ci.yml               # UPDATED: two jobs, E2E service containers
pyproject.toml                          # UPDATED: pytest markers declared
```

---

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Session-scoped MCP server fixture | SC-002: 60s budget for integration suite; fresh server per test would take 100ms+ startup × 9+ tests | No way to share server state without session scope while maintaining per-test isolation |
| Two CI jobs instead of one | Separating fast (no Docker) from slow (Docker service containers) keeps PR feedback loop fast for the unit+integration tier | Single job would add Docker spin-up time to every run including quick lint/unit fixes |

---

## Delivery Phases

> **Phase Pause Gates**: After each commit group, push to GitHub and wait for CI to go green before proceeding to the next phase. This is a hard gate — no cowboy skips.

---

### Phase A — Test Infrastructure + Conftest Fixtures

**Goal**: Lay the foundation. No new tests yet — just the machinery that makes the new tiers possible.

**Deliverables**:
1. `pyproject.toml` — add `integration` and `e2e` pytest markers
2. `tests/integration/conftest.py` — session-scoped `mcp_server` fixture using anyio memory streams + `ClientSession`
3. `tests/e2e/__init__.py` + `tests/e2e/conftest.py` — E2E gating logic (`PMPROXY_URL`/`SKIP_E2E`) + session-scoped `e2e_session` fixture using `stdio_client`
4. `tests/e2e/test_live.py` — relocate existing `tests/integration/test_integration.py` content here, replace `skipif` marker with the new `SKIP_E2E` gating pattern, add `@pytest.mark.e2e`
5. `docker-compose.yml` — `performancecopilot/pcp` + `redis/redis-stack` with pmproxy pointed at redis-stack

**TDD note**: The conftest fixtures are the code under "test" here. Write a canary test that confirms the session fixture starts and the E2E gating raises the right error before writing any tool tests.

**Commit**: `test: add integration + e2e test infrastructure and conftest fixtures`

**⏸ PAUSE GATE A**: Push to `002-add-integration-e2e-tests`. Verify:
- `unit-integration` job: lint, format, unit + contract tests all green
- `e2e` job: E2E tests skip cleanly (no `PMPROXY_URL` in default CI runner) OR fail with the expected diagnostic — check job is configured correctly
- Coverage gate ≥80% still passes

---

### Phase B — Integration Tests: All Nine Tools

**Goal**: Full MCP protocol coverage for all nine tools using the session-scoped server fixture and respx mocks. Every tool must return a valid, well-formed MCP response.

**Deliverables** (one file per tool group, TDD throughout — write failing test, then make it pass):
1. `tests/integration/test_hosts.py` — `pcp_get_hosts` happy path
2. `tests/integration/test_live.py` — `pcp_fetch_live` happy path
3. `tests/integration/test_timeseries.py` — `pcp_fetch_timeseries` + `pcp_query_series`
4. `tests/integration/test_search.py` — `pcp_search`
5. `tests/integration/test_discovery.py` — `pcp_discover_metrics` (prefix mode + search mode) + `pcp_get_metric_info`
6. `tests/integration/test_derived.py` — `pcp_derive_metric`
7. `tests/integration/test_comparison.py` — `pcp_compare_windows`

**Each test must**:
- Call the tool via `session.call_tool(tool_name, args)` — not `_*_impl()` directly
- Assert the response is not an MCP error (`isError` absent or false)
- Assert the response contains the expected shape (e.g., `items` list, `results` key, etc.)
- Use `respx.mock` per-test to provide pmproxy HTTP responses

**Delete** `tests/integration/test_integration.py` — content already relocated to `tests/e2e/test_live.py` in Phase A.

**Commit**: `test: add integration tests for all nine MCP tools via protocol dispatch`

**⏸ PAUSE GATE B**: Push to `002-add-integration-e2e-tests`. Verify:
- `unit-integration` job: all integration tests pass, full suite green
- Integration suite completes within 60s (SC-002) — check CI job timing
- Coverage ≥80% maintained
- Each tool listed in the test run output separately (readable failure attribution)

---

### Phase C — E2E Subprocess Harness + Initial Tool Coverage

**Goal**: Prove the subprocess harness works end-to-end. Initial coverage of three tools against the real PCP container in CI.

**Deliverables**:
1. `.github/workflows/ci.yml` — add `e2e` job with `services:` for `performancecopilot/pcp` and `redis/redis-stack`, `PMPROXY_URL` env, pmproxy readiness wait step
2. `tests/e2e/test_tools.py` — E2E tests for initial tool set: `pcp_fetch_live`, `pcp_get_hosts`, `pcp_fetch_timeseries` (metrics: `kernel.all.load`, `mem.util.used`)

**TDD note**: By this phase, `docker-compose.yml` is already in place from Phase A. Bring the stack up locally (`docker compose up -d`) before writing any E2E tests — infrastructure not running is not a valid red state, it's just broken scaffolding.

Write each test with a deliberately wrong assertion first so it fails for the right reason against the live stack. For example, assert `result["items"] == []` for a tool you know returns data — it fails because items is non-empty, proving the full subprocess → MCP → pmproxy → PCP stack is wired up correctly. Then fix the assertion to `assert len(result["items"]) > 0` and watch it go green. That's your red-green cycle.

**Commit**: `test: add E2E subprocess harness and initial tool coverage with GHA service containers`

**⏸ PAUSE GATE C**: Push to `002-add-integration-e2e-tests`. Verify:
- `unit-integration` job: still green
- `e2e` job: PCP + redis-stack spin up successfully; `pcp_fetch_live`, `pcp_get_hosts`, `pcp_fetch_timeseries` return real data; job passes
- Failure in E2E job correctly blocks PR merge (check branch protection settings)

---

### Phase D — Remaining E2E Tool Coverage

**Goal**: Extend E2E coverage to all nine tools. Feature complete.

**Deliverables**:
1. `tests/e2e/test_tools.py` — extend with remaining tools: `pcp_query_series`, `pcp_search`, `pcp_discover_metrics` (prefix + search), `pcp_get_metric_info`, `pcp_derive_metric`, `pcp_compare_windows`
2. Verify `pcp_search` works (requires RediSearch from redis-stack)
3. Final coverage check — confirm ≥80% gate with all new tests

**Commit**: `test: complete E2E coverage for all nine MCP tools`

**⏸ PAUSE GATE D (Final)**: Push to `002-add-integration-e2e-tests`. Verify:
- Both CI jobs green
- All three tiers (unit, integration, E2E) reported separately in CI output
- SC-001 through SC-006 all satisfied
- Ready to open PR to `main`

---

## Key Technical Decisions

### In-Process MCP Transport (Integration Tests)

```python
# tests/integration/conftest.py
import anyio
import pytest
from mcp.client.session import ClientSession
from mcp.shared.message import SessionMessage

import pmmcp.server as server_module
from pmmcp.config import PmproxyConfig

@pytest.fixture(scope="session")
def mcp_server():
    """One FastMCP instance for the whole integration test session."""
    server_module._config = PmproxyConfig(url="http://mock-pmproxy:44322", timeout=5.0)
    return server_module.mcp

@pytest.fixture
async def mcp_session(mcp_server):
    """Fresh ClientSession over memory streams for each test."""
    client_r, server_w = anyio.create_memory_object_stream[SessionMessage | Exception](0)
    server_r, client_w = anyio.create_memory_object_stream[SessionMessage | Exception](0)
    init_opts = mcp_server._mcp_server.create_initialization_options()

    async with anyio.create_task_group() as tg:
        tg.start_soon(
            mcp_server._mcp_server.run, server_r, server_w, init_opts
        )
        async with ClientSession(client_r, client_w) as session:
            await session.initialize()
            yield session
            tg.cancel_scope.cancel()
```

### E2E Gating Logic

```python
# tests/e2e/conftest.py
import os
import pytest

PMPROXY_URL = os.environ.get("PMPROXY_URL")
SKIP_E2E = os.environ.get("SKIP_E2E", "0") == "1"

def pytest_collection_modifyitems(items):
    for item in items:
        if "e2e" in item.nodeid:
            if SKIP_E2E:
                item.add_marker(pytest.mark.skip(reason="E2E opt-out: SKIP_E2E=1"))
            elif not PMPROXY_URL:
                item.add_marker(
                    pytest.mark.xfail(
                        strict=True,
                        reason="PMPROXY_URL is required for E2E tests. Set SKIP_E2E=1 to explicitly opt out.",
                    )
                )
```

### CI Job Structure

```yaml
jobs:
  unit-integration:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync --extra dev
      - run: uv run ruff check src/ tests/
      - run: uv run ruff format --check src/ tests/
      - run: uv run pytest -m "not e2e" --cov=pmmcp --cov-fail-under=80 --junitxml=results-unit-integration.xml

  e2e:
    runs-on: ubuntu-latest
    services:
      pcp:
        image: performancecopilot/pcp:latest
        ports: ["44322:44322"]
      redis-stack:
        image: redis/redis-stack:latest
        ports: ["6379:6379"]
    env:
      PMPROXY_URL: http://localhost:44322
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync --extra dev
      - name: Wait for pmproxy
        run: |
          for i in $(seq 1 30); do
            curl -sf http://localhost:44322/pmapi/context?hostspec=localhost && break
            sleep 2
          done
      - run: uv run pytest -m e2e --junitxml=results-e2e.xml
```
