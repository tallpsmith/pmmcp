# Data Model: Integration and E2E Test Suites

**Branch**: `002-add-integration-e2e-tests` | **Date**: 2026-02-25

> This feature adds test infrastructure only — no production data models change.
> This document captures the test fixture models, configuration entities, and state machines.

---

## Test Configuration Entities

### IntegrationServerFixture

Session-scoped. One instance per pytest session, shared across all integration tests.

| Field | Type | Description |
|-------|------|-------------|
| `mcp` | `FastMCP` | The pmmcp server instance (imported from `pmmcp.server`) |
| `init_options` | `InitializationOptions` | Captured from `mcp._mcp_server.create_initialization_options()` |

**Lifecycle**: Created once at session start (via `@pytest.fixture(scope="session")`), torn down at session end.

**Isolation guarantee**: Each test creates its own `ClientSession` over fresh memory streams. The server instance is reused; only the transport layer is per-test.

---

### E2EConfig

| Field | Type | Source | Default |
|-------|------|--------|---------|
| `pmproxy_url` | `str` | `PMPROXY_URL` env var | — (required or fail) |
| `skip_e2e` | `bool` | `SKIP_E2E` env var | `False` |
| `timeout_seconds` | `float` | hardcoded | `30.0` |

**State machine**:
```
PMPROXY_URL set?
  NO  → SKIP_E2E=1?
          YES → pytest.skip("E2E opt-out: SKIP_E2E=1")
          NO  → pytest.fail("PMPROXY_URL required. Set SKIP_E2E=1 to opt out.")
  YES → SKIP_E2E=1?
          YES → pytest.skip("E2E opt-out: SKIP_E2E=1")
          NO  → run E2E tests
```

---

### SubprocessHarness

Per-test. Manages the pmmcp subprocess lifecycle for E2E tests.

| Field | Type | Description |
|-------|------|-------------|
| `params` | `StdioServerParameters` | `command="uv"`, `args=["run","python","-m","pmmcp"]` |
| `env` | `dict[str, str]` | `os.environ | {"PMPROXY_URL": pmproxy_url}` |
| `session` | `ClientSession` | Active MCP session over stdio |

**Lifecycle**: Created per E2E test via `@pytest.fixture` (function-scoped). Subprocess is terminated in fixture teardown.

---

## Tool Coverage Matrix

Tracks which tools are exercised by each test tier.

| Tool | Unit ✓ | Contract ✓ | Integration (new) | E2E (new) |
|------|--------|-----------|-------------------|-----------|
| `pcp_get_hosts` | ✓ | ✓ | Phase 1 | Phase 2 |
| `pcp_fetch_live` | ✓ | ✓ | Phase 1 | Phase 2 |
| `pcp_fetch_timeseries` | ✓ | ✓ | Phase 1 | Phase 2 |
| `pcp_query_series` | ✓ | ✓ | Phase 1 | Phase 2 |
| `pcp_search` | ✓ | ✓ | Phase 1 | Phase 2 |
| `pcp_derive_metric` | ✓ | ✓ | Phase 1 | Phase 2 |
| `pcp_discover_metrics` (prefix) | ✓ | ✓ | Phase 1 | Phase 2 |
| `pcp_discover_metrics` (search) | ✓ | ✓ | Phase 1 | Phase 2 |
| `pcp_get_metric_info` | ✓ | ✓ | Phase 1 | Phase 2 |

---

## Directory Layout (after feature complete)

```
tests/
├── conftest.py                    # Shared fixtures (existing, extended)
├── unit/                          # Existing unit tests (unchanged)
├── contract/                      # Existing contract tests (unchanged)
├── integration/                   # NEW: MCP protocol dispatch tests
│   ├── __init__.py
│   ├── conftest.py                # Session-scoped MCP server fixture
│   └── test_<tool_group>.py × 5  # One file per tool group
└── e2e/                           # NEW: Subprocess + real PCP tests
    ├── __init__.py
    ├── conftest.py                # E2E gating + subprocess harness fixture
    ├── test_live.py               # Relocated from tests/integration/test_integration.py
    └── test_<tool>.py × n        # Per-tool E2E scenarios

docker-compose.yml                 # NEW: pcp + redis-stack for local E2E
.github/workflows/ci.yml           # UPDATED: two jobs, service containers
pyproject.toml                     # UPDATED: markers, new deps if any
```

---

## Pytest Marker Taxonomy

| Marker | Applied To | Meaning |
|--------|-----------|---------|
| `@pytest.mark.integration` | All tests in `tests/integration/` | In-process MCP protocol tests |
| `@pytest.mark.e2e` | All tests in `tests/e2e/` | Subprocess + real PCP tests |
| (no marker) | `tests/unit/`, `tests/contract/` | Fast isolated tests |

**pytest.ini config** (additive to existing):
```toml
[tool.pytest.ini_options]
markers = [
    "integration: in-process MCP protocol tests (mocked pmproxy)",
    "e2e: subprocess full-stack tests (requires PMPROXY_URL or SKIP_E2E=1)",
]
```

---

## CI Job Structure

```
job: unit-integration
  runs-on: ubuntu-latest
  steps: checkout → uv sync → lint → format-check → test (unit + integration)
  coverage gate: ≥80%

job: e2e
  runs-on: ubuntu-latest
  services:
    pcp:         performancecopilot/pcp:latest  (port 44322)
    redis-stack: redis/redis-stack:latest       (port 6379)
  env:
    PMPROXY_URL: http://localhost:44322
  steps: checkout → uv sync → e2e-wait-for-pcp → pytest -m e2e
```

**Reporting separation**: `--junitxml=results-{tier}.xml` per job so unit, integration, and E2E results appear as distinct check suites in GitHub.
