# Research: Integration and E2E Test Suites

**Branch**: `002-add-integration-e2e-tests` | **Date**: 2026-02-25

---

## In-Process MCP Protocol Testing

**Decision**: Use `anyio` memory streams + `mcp.client.session.ClientSession` + `fastmcp._mcp_server.run()` for in-process integration tests.

**Rationale**: The MCP SDK (v1.26.0) exposes a low-level `Server.run(read_stream, write_stream, ...)` API that accepts `anyio.streams.memory` streams directly. `FastMCP._mcp_server` provides the underlying server instance. This gives a true MCP protocol dispatch path (tool registration → dispatch → response serialisation) with zero network overhead and full respx-based httpx mocking for the pmproxy tier.

**Pattern**:
```python
import anyio
from mcp.client.session import ClientSession
from mcp.shared.message import SessionMessage

# Create cross-wired memory streams
client_r, server_w = anyio.create_memory_object_stream[SessionMessage | Exception](0)
server_r, client_w = anyio.create_memory_object_stream[SessionMessage | Exception](0)

async with anyio.create_task_group() as tg:
    tg.start_soon(mcp._mcp_server.run, server_r, server_w, init_options)
    async with ClientSession(client_r, client_w) as session:
        await session.initialize()
        result = await session.call_tool("pcp_fetch_live", {...})
```

**Server exception propagation**: `Server.run(raise_exceptions=True)` causes tool errors to propagate as exceptions rather than hiding in MCP error responses — critical for diagnosing test failures.

**Alternatives considered**:
- `pytest-httpserver`: Would only mock at HTTP level. Rejected — `respx` already in dev deps and mocks at httpx transport level (same effect, no new dependency).
- Fresh server per test: Rejected per FR-013 — violates 60s budget (SC-002). Session-scoped server is the answer.
- `mcp.client.stdio.stdio_client` for integration: Overkill for in-process — subprocess launch is E2E territory.

---

## Session-Scoped Server Fixture Strategy

**Decision**: One `FastMCP` server instance per pytest session; per-test isolation via respx mock scope.

**Rationale**: Server startup (lifespan, httpx client init) takes ~100ms. With 9+ integration tests × fresh server = several seconds minimum. Session scope keeps the integration suite well inside SC-002's 60s budget.

**Per-test isolation mechanism**: Each test wraps its tool call in its own `respx.mock` context, overriding the exact endpoints it needs. Because each test creates a fresh `ClientSession` over the same memory streams, state doesn't bleed between tests.

**Complication**: The existing `server.py` uses module-level `_config` and `_client` globals set before `mcp.run()`. The test fixture must inject config before the lifespan runs, then reset after. This is testable because the lifespan is an async context manager.

---

## HTTP Mock Library

**Decision**: Continue using `respx` (already in dev dependencies).

**Rationale**: `respx` mocks at the httpx transport layer, which is exactly what `PmproxyClient` uses. No new dependency needed. Pattern is already established in `tests/conftest.py` and all unit tests.

**Alternative considered**: `pytest-httpserver` — binds a real TCP port, heavier weight, unnecessary for our use case. Rejected.

---

## E2E Subprocess Transport

**Decision**: Use `mcp.client.stdio.stdio_client` with `StdioServerParameters` to drive a pmmcp subprocess.

**Rationale**: This is exactly the transport Claude Desktop/Claude Code uses. Highest-fidelity test possible. `subprocess.Popen` with stdin/stdout pipes would work too but `stdio_client` handles the async message framing automatically.

**Pattern**:
```python
from mcp.client.stdio import stdio_client, StdioServerParameters

params = StdioServerParameters(
    command="uv",
    args=["run", "python", "-m", "pmmcp"],
    env={"PMPROXY_URL": pmproxy_url, ...},
)
async with stdio_client(params) as (r, w):
    async with ClientSession(r, w) as session:
        await session.initialize()
        result = await session.call_tool("pcp_fetch_live", {...})
```

---

## E2E Environment Gating

**Decision**: Hard-fail when `PMPROXY_URL` unset and `SKIP_E2E` unset; silent skip only on `SKIP_E2E=1`.

**Rationale**: Matches FR-006 and SC-004 exactly. Silent skips are the enemy — they give false confidence. The hard-fail surfaces the problem immediately. `SKIP_E2E=1` is the explicit opt-out with a visible message.

**Implementation**: Custom pytest plugin (`conftest.py` in `tests/e2e/`) using `pytest_collection_modifyitems` or a session-scoped autouse fixture that fails early with a clear diagnostic.

---

## Docker Compose for Local E2E

**Decision**: `docker-compose.yml` at repo root with `performancecopilot/pcp` and `redis/redis-stack` services.

**Rationale**: FR-014 mandates a single-command local E2E setup. `redis/redis-stack` provides RediSearch (required for `pcp_search` / `pcp_discover_metrics` search mode). The base PCP image ships Valkey but without RediSearch module — confirmed by HTTP 400 on `/search/text` against live instance.

**pmproxy redis config**: pmproxy must be pointed at the `redis-stack` container. This is done via environment variable `PCP_REDIS_HOST=redis-stack:6379` or pmproxy config file injection.

---

## GitHub Actions Service Containers

**Decision**: Two GHA `services:` entries — `performancecopilot/pcp` and `redis/redis-stack` — with E2E job separate from unit/integration job.

**Rationale**: Keeps the unit+integration job fast (no Docker spin-up). The E2E job uses service containers and sets `PMPROXY_URL=http://localhost:44322`. Failure in either job blocks the PR.

**CI structure**:
```
jobs:
  unit-integration:   # always runs, no Docker, ~60s target
  e2e:                # always runs, requires service containers, ~3-5min
```

**Alternative considered**: Single job with services — rejected because services add startup time to every run, penalising the fast unit+integration feedback loop.

---

## Existing `tests/integration/` Conflict

**Decision**: Rename existing `tests/integration/test_integration.py` to `tests/e2e/test_live.py` as part of commit group 1.

**Rationale**: The current "integration" tests call `_*_impl()` functions directly against a live pmproxy. That's the E2E pattern, not the MCP-protocol integration pattern the spec defines. Moving them to `tests/e2e/` correctly categorises them and avoids confusion.

**Action required on relocation**: The existing tests use `pytest.mark.skipif(not PMPROXY_URL, ...)` which silently skips when `PMPROXY_URL` is absent. That pattern must be **deleted** when the tests move to `tests/e2e/`. The new `tests/e2e/conftest.py` gating takes over: no `PMPROXY_URL` + no `SKIP_E2E` = hard fail; `SKIP_E2E=1` = explicit skip with a visible message. The old silent-skip behaviour is replaced by a require-or-explain model.

---

## Approved Safe Metrics for E2E

**Decision**: `kernel.all.load` (1/5/15min load), `mem.util.used`, `mem.util.free`, `kernel.percpu.cpu.user`.

**Rationale**: FR-007 restricts E2E to metrics guaranteed available in containerised/VM environments. These are always present on any Linux host. Avoid metrics requiring physical hardware inventory (disk spindle counts, NIC speeds, NUMA topology).
