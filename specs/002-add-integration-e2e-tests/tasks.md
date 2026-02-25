# Tasks: Integration and E2E Test Suites

**Input**: Design documents from `specs/002-add-integration-e2e-tests/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓

**Commit discipline**: Four commit groups matching plan phases A → B → C → D. Each group must be a coherent, reviewable unit with CI green before proceeding.

## Format: `[ID] [P?] [Story?] Description with file path`

- **[P]**: Can run in parallel (different files, no blocking dependencies)
- **[US1/2/3]**: Maps task to user story from spec.md
- No story label = Setup or Foundational task

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Configuration changes and local dev tooling that enable the new test tiers. No test code yet.

**Commit**: `test: add integration + e2e test infrastructure and conftest fixtures` *(shared with Phase 2)*

- [X] T001 Update `pyproject.toml`: add `integration` and `e2e` entries to `[tool.pytest.ini_options] markers` list; add `asyncio_mode = "auto"` if not already present
- [X] T002 [P] Create `docker-compose.yml` at repo root: `performancecopilot/pcp:latest` on port 44322 and `redis/redis-stack:latest` on port 6379; set pmproxy env `PCP_REDIS_HOST=redis-stack:6379` so all nine tools are exercisable locally

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Test fixtures and harnesses that ALL user story test phases depend on. Nothing in Phase 3, 4, or 5 can run until this phase is complete.

**⚠️ CRITICAL**: US1 integration tests require T003–T004; US2/US3 E2E tests require T005–T007.

**Commit**: `test: add integration + e2e test infrastructure and conftest fixtures` *(shared with Phase 1)*

- [X] T003 Create `tests/integration/conftest.py`: session-scoped `mcp_server` fixture that injects `PmproxyConfig(url="http://mock-pmproxy:44322", timeout=5.0)` into `pmmcp.server._config` and returns `server_module.mcp`; async per-test `mcp_session` fixture that creates cross-wired `anyio.create_memory_object_stream[SessionMessage | Exception](0)` pairs, starts `mcp._mcp_server.run(server_r, server_w, init_opts, raise_exceptions=True)` in a task group, and yields an initialised `ClientSession`
- [X] T004 Add canary integration test to `tests/integration/test_canary.py`: one async test using `mcp_session` that calls `session.list_tools()` and asserts exactly 9 tools are returned — confirms fixture wiring before any tool test is written; mark `@pytest.mark.integration`
- [X] T005 [P] Create `tests/e2e/__init__.py` (empty — module marker only)
- [X] T006 Create `tests/e2e/conftest.py`: implement `pytest_collection_modifyitems` gating — if item nodeid contains `e2e`: when `SKIP_E2E=1` add `pytest.mark.skip(reason="E2E opt-out: SKIP_E2E=1")`; when `PMPROXY_URL` unset add `pytest.mark.xfail(strict=True, reason="PMPROXY_URL is required for E2E tests. Set SKIP_E2E=1 to explicitly opt out.")`; add async session-scoped `e2e_session` fixture using `mcp.client.stdio.stdio_client(StdioServerParameters(command="uv", args=["run","python","-m","pmmcp"], env=os.environ | {"PMPROXY_URL": PMPROXY_URL}))` that yields an initialised `ClientSession`
- [X] T007 Relocate `tests/integration/test_integration.py` to `tests/e2e/test_live.py`: replace `@pytest.mark.skipif(not PMPROXY_URL, ...)` with `@pytest.mark.e2e`; remove all manual skip logic (gating now handled by `tests/e2e/conftest.py`); update any direct `_*_impl()` calls to use the `e2e_session` fixture and `session.call_tool()`; then **delete** the original `tests/integration/test_integration.py`

**⏸ PAUSE GATE A**: Push branch. Verify: unit-integration CI job green (lint, format, unit + contract + canary); E2E job xfail-with-diagnostic (no `PMPROXY_URL` in default runner); coverage ≥80%.

---

## Phase 3: User Story 1 — MCP Protocol Path Verification (Priority: P1) 🎯 MVP

**Goal**: All nine MCP tools exercised through real MCP protocol dispatch (tool registration → server dispatch → HTTP mock → MCP-formatted response). Zero dependency on any running service.

**Independent Test**: `uv run pytest tests/integration/ -m integration` on any CI runner with no PCP/Docker — all nine tools must return non-error MCP responses.

**Commit**: `test: add integration tests for all nine MCP tools via protocol dispatch`

> **TDD cycle per test file**: write the test → run it (it fails with "tool not found" or assertion error) → confirm failure is correct → run full suite → confirm green.

- [X] T008 [P] [US1] Write `tests/integration/test_hosts.py`: `@pytest.mark.integration` async test calling `session.call_tool("pcp_get_hosts", {})` with `respx.mock` patching `/pmapi/context` (200, `{"context":1}`) and `/series/instances` (200, `[{"instance":0,"name":"localhost"}]`); assert `result.isError` is falsy and response text contains `"hosts"` or `"localhost"`
- [X] T009 [P] [US1] Write `tests/integration/test_live.py`: `@pytest.mark.integration` async test calling `session.call_tool("pcp_fetch_live", {"metrics":["kernel.all.load"]})` with `respx.mock` patching `/pmapi/context` and `/pmapi/fetch` (200, realistic fetch payload with `values` list); assert non-error response containing metric values
- [X] T010 [P] [US1] Write `tests/integration/test_timeseries.py`: two `@pytest.mark.integration` async tests — one for `pcp_fetch_timeseries` (respx mocks for `/series/query` + `/series/values`, assert timeseries data in response) and one for `pcp_query_series` (respx mock for `/series/query`, assert series identifiers in response)
- [X] T011 [P] [US1] Write `tests/integration/test_search.py`: `@pytest.mark.integration` async test calling `session.call_tool("pcp_search", {"query":"kernel"})` with `respx.mock` patching `/search/text` (200, `{"results":[{"name":"kernel.all.load","text":"..."}]}`); assert non-error response with `"kernel"` in text
- [X] T012 [P] [US1] Write `tests/integration/test_discovery.py`: three `@pytest.mark.integration` async tests — `pcp_discover_metrics` prefix mode (respx mock for `/pmapi/children`, assert namespace list), `pcp_discover_metrics` search mode (respx mock for `/search/text`, assert results), `pcp_get_metric_info` (respx mocks for `/pmapi/metric` + `/pmapi/indom`, assert metadata fields present)
- [X] T013 [P] [US1] Write `tests/integration/test_derived.py`: `@pytest.mark.integration` async test calling `session.call_tool("pcp_derive_metric", {"name":"test.derived","expr":"kernel.all.load"})` with `respx.mock` patching `/pmapi/derive` (200 or expected response shape); assert non-error MCP response
- [X] T014 [P] [US1] Write `tests/integration/test_comparison.py`: `@pytest.mark.integration` async test calling `session.call_tool("pcp_compare_windows", {"metric":"mem.util.used","baseline_start":"...","comparison_start":"...",...})` with `respx.mock` patching `/series/query` and `/series/values` twice (two time windows); assert non-error response with comparison statistics

**⏸ PAUSE GATE B**: Push branch. Verify: all 7 integration test files pass; integration suite completes under 60 seconds (check CI job timing); coverage ≥80%; each tool appears distinctly in test output.

---

## Phase 4: User Story 2 — Full-Stack Regression Detection (Priority: P2)

**Goal**: pmmcp launched as a real subprocess over stdio, communicating with a live containerised PCP instance. Real metric data flows end-to-end.

**Independent Test**: Bring up `docker compose up -d`, set `PMPROXY_URL=http://localhost:44322`, run `uv run pytest tests/e2e/ -m e2e` — all tools must return real metric data.

**Commit**: `test: add E2E subprocess harness and initial tool coverage with GHA service containers` *(T015)*
**Commit**: `test: complete E2E coverage for all nine MCP tools` *(T016)*

> **TDD cycle**: bring up docker-compose locally first; write assertion with deliberately wrong expected value to confirm full stack is wired; fix assertion to correct value and watch it go green.

- [X] T015 [US2] Create `tests/e2e/test_tools.py` with initial 3 `@pytest.mark.e2e` async tests using `e2e_session` fixture: `test_fetch_live` calls `pcp_fetch_live` with `{"metrics":["kernel.all.load"]}` and asserts `len(values) > 0`; `test_get_hosts` calls `pcp_get_hosts` and asserts at least one host returned; `test_fetch_timeseries` calls `pcp_fetch_timeseries` with `{"metrics":["mem.util.used"],"start":"-2m","finish":"now","interval":"10s"}` and asserts data points present — only use FR-007-approved metrics throughout
- [X] T016 [US2] Extend `tests/e2e/test_tools.py` with remaining 6 `@pytest.mark.e2e` async tests: `test_query_series` (`pcp_query_series`, assert series IDs returned); `test_search` (`pcp_search` with `{"query":"kernel"}`, asserts RediSearch results — requires redis-stack); `test_discover_metrics_prefix` (`pcp_discover_metrics` prefix mode `{"prefix":"kernel"}`, assert namespace children); `test_discover_metrics_search` (`pcp_discover_metrics` search mode, assert concept results); `test_get_metric_info` (`pcp_get_metric_info` for `kernel.all.load`, assert metadata); `test_compare_windows` (`pcp_compare_windows`, assert delta statistics present)

**⏸ PAUSE GATE C**: Push branch. Verify: unit-integration job still green; E2E job: PCP + redis-stack spin up; initial 3 tools return real data; job passes; E2E failure correctly blocks PR merge.

---

## Phase 5: User Story 3 — Continuous E2E Verification in GitHub Actions (Priority: P2)

**Goal**: GitHub Actions CI pipeline automatically runs E2E tests on every PR against a containerised PCP + redis-stack. Failures block merge.

**Independent Test**: Open a PR; verify two separate CI jobs appear — `unit-integration` (always runs, no Docker) and `e2e` (runs with service containers, reports separately).

**Commit**: included in `test: add E2E subprocess harness and initial tool coverage with GHA service containers`

- [X] T017 [US3] Update `.github/workflows/ci.yml`: (1) rename/update existing job to `unit-integration` — add `-m "not e2e"` filter to pytest command and `--junitxml=results-unit-integration.xml`; (2) add `e2e` job with `services: pcp: {image: performancecopilot/pcp:latest, ports: ["44322:44322"]}` and `redis-stack: {image: redis/redis-stack:latest, ports: ["6379:6379"]}`, `env: PMPROXY_URL: http://localhost:44322`, a readiness step (`for i in $(seq 1 30); do curl -sf http://localhost:44322/pmapi/context?hostspec=localhost && break; sleep 2; done`), and `uv run pytest -m e2e --junitxml=results-e2e.xml`

**⏸ PAUSE GATE D (Final)**: Push branch. Verify: both CI jobs green; three test tiers (unit, integration, E2E) reported separately; SC-001 through SC-006 all satisfied; PR ready to merge to `main`.

---

## Final Phase: Polish & Cross-Cutting Concerns

- [X] T018 [P] Run `uv run ruff check tests/integration/ tests/e2e/` and `uv run ruff format --check tests/integration/ tests/e2e/` — fix any violations in new test files
- [X] T019 Confirm coverage gate: `uv run pytest -m "not e2e" --cov=pmmcp --cov-fail-under=80 --cov-report=term-missing` passes without modification to production code

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately; T001 and T002 are parallel
- **Foundational (Phase 2)**: Depends on Phase 1 — T003 and T005+T006 can start in parallel; T007 depends on T006
- **US1 (Phase 3)**: Depends on T003+T004 (integration conftest) — all 7 test files [P] once conftest is ready
- **US2 (Phase 4)**: Depends on T005+T006+T007 (e2e conftest + relocation) — T015 then T016 sequentially
- **US3 (Phase 5)**: Depends on T015 (at least initial E2E tests exist) — T017 can be drafted in parallel with T016
- **Polish (Final)**: Depends on all preceding phases

### User Story Dependencies

- **US1 (P1)**: Blocked only by T003–T004 (integration conftest). Independent of US2/US3.
- **US2 (P2)**: Blocked only by T005–T007 (e2e conftest + relocation). Independent of US1.
- **US3 (P2)**: Blocked by T015 (first E2E tests must exist before CI workflow is meaningful). Depends on US2.

### Parallel Opportunities Within Each Phase

- Phase 1: T001 ∥ T002
- Phase 2: T003 ∥ (T005 → T006 → T007)
- Phase 3: T008 ∥ T009 ∥ T010 ∥ T011 ∥ T012 ∥ T013 ∥ T014 (all seven test files are independent)
- Phase 4: T015 → T016 (sequential — both write to the same file)
- Phase 5: T017 can overlap with T016 if drafted separately

---

## Parallel Example: Phase 3 (US1 Integration Tests)

```bash
# All seven integration test files are independent — launch together:
Task: "Write tests/integration/test_hosts.py"        # T008
Task: "Write tests/integration/test_live.py"         # T009
Task: "Write tests/integration/test_timeseries.py"   # T010
Task: "Write tests/integration/test_search.py"       # T011
Task: "Write tests/integration/test_discovery.py"    # T012
Task: "Write tests/integration/test_derived.py"      # T013
Task: "Write tests/integration/test_comparison.py"   # T014
```

---

## Implementation Strategy

### MVP First (US1 Only — Integration Tier)

1. Complete Phase 1: Setup (T001, T002)
2. Complete Phase 2: Foundational (T003–T007)
3. Complete Phase 3: US1 integration tests (T008–T014)
4. **STOP and VALIDATE**: `uv run pytest tests/integration/ -m integration` — all nine tools green, CI green at Pause Gate B
5. Integration tier is independently shippable at this point

### Full Delivery (All Three User Stories)

1. Setup + Foundational → Pause Gate A
2. US1 integration tests → Pause Gate B (MVP)
3. US2 initial E2E (T015) + US3 CI workflow (T017) → Pause Gate C
4. US2 remaining E2E (T016) → Pause Gate D (feature complete)
5. Polish (T018, T019)

---

## Task Summary

| Phase | Tasks | Story | Parallelisable |
|-------|-------|-------|----------------|
| Setup | T001–T002 | — | T001 ∥ T002 |
| Foundational | T003–T007 | — | T003 ∥ (T005→T006→T007) |
| US1 Integration | T008–T014 | US1 | All 7 in parallel |
| US2 E2E | T015–T016 | US2 | Sequential (same file) |
| US3 CI | T017 | US3 | Can overlap T016 |
| Polish | T018–T019 | — | T018 ∥ T019 |
| **Total** | **19 tasks** | | |

**Suggested MVP**: Phases 1–3 (T001–T014) — delivers complete US1 integration tier independently.
