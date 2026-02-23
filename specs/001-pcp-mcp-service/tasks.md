# Tasks: PCP MCP Service (pmmcp)

**Input**: Design documents from `/specs/001-pcp-mcp-service/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/mcp-tools.md ✅, contracts/pmproxy-api.md ✅, quickstart.md ✅

**Tests**: Per the project constitution (Principle II — Testing Standards, NON-NEGOTIABLE), tests are mandatory. Unit coverage MUST reach ≥ 80% and contract tests MUST accompany any interface change. Test tasks below MUST be included; follow TDD: write tests first, verify they FAIL, then implement.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in all descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, directory structure, packaging, and CI skeleton

- [X] T001 Create project directory structure: `src/pmmcp/`, `src/pmmcp/tools/`, `tests/unit/`, `tests/integration/`, `tests/contract/`, `agents/` (with `__init__.py` stubs in each Python package directory)
- [X] T002 Create `pyproject.toml` with PEP 621 metadata (`name="pmmcp"`, `version="0.1.0"`, `requires-python=">=3.11"`), runtime dependencies (`mcp[cli]>=1.2.0`, `pydantic>=2.0`, `pydantic-settings`, `httpx>=0.27`), dev extras (`pytest`, `pytest-asyncio`, `respx`, `ruff`, `pytest-cov`), and `[project.scripts]` entry `pmmcp = "pmmcp.__main__:main"`
- [X] T003 [P] Add `[tool.ruff]` configuration section to `pyproject.toml`: `line-length=100`, `select=["E","F","I","UP"]`, `target-version="py311"`; add `[tool.pytest.ini_options]` with `asyncio_mode="auto"` and `testpaths=["tests"]`
- [X] T004 [P] Create `Dockerfile`: multi-stage build — build stage installs dependencies via `uv pip install`; runtime stage uses `python:3.11-slim`; no port exposed (stdio transport); default `CMD ["python", "-m", "pmmcp"]`; no `-t` tty flag (stdio JSON-RPC is not terminal-based)
- [X] T005 [P] Create `.mcp.json.example` with three MCP server configuration variants: Docker (`docker run -i --rm ghcr.io/<org>/pmmcp`), uvx (`uvx pmmcp`), and python-m (`python -m pmmcp`) modes, each with `--pmproxy-url` arg, per `quickstart.md`
- [X] T006 [P] Create `.github/workflows/ci.yml`: runs on push/PR; steps: `ruff check src/ tests/`, `ruff format --check src/ tests/`, `pytest --cov=pmmcp --cov-fail-under=80`; Python 3.11 matrix

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core shared infrastructure that MUST be complete before any user story tool can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T007 Create `src/pmmcp/__init__.py` exporting `__version__ = "0.1.0"`
- [X] T008 [P] Implement `src/pmmcp/config.py`: `PmproxyConfig(BaseSettings)` with `url: AnyHttpUrl` and `timeout: float = 30.0`; env prefix `PMPROXY_`; fields structured as object (not flat URL string) to accommodate future `username`/`password` fields without breaking changes per `data-model.md`
- [X] T009 Implement `src/pmmcp/models.py`: all Pydantic v2 models from `data-model.md` — `Host`, `Metric`, `Instance`, `MetricValue`, `TimeWindow`, `WindowStats`, `DeltaStats`, `WindowComparison`, `SearchResult`, and generic `PaginatedResponse[T]`; include validation rules (`AnyHttpUrl` for config url, dot-separated name validator for `Metric.name`, `TimeWindow.interval` must be duration string or `"auto"`, `PaginatedResponse.limit` 1–1000 via `Field(ge=1, le=1000)`, `PaginatedResponse.offset` ≥ 0)
- [X] T010 [P] Implement `src/pmmcp/utils.py`: `resolve_interval(start: str, end: str, interval: str) -> str` with auto-mapping (≤1h→"15s", ≤24h→"5min", ≤7d→"1hour", >7d→"6hour") per `research.md` Decision 8; `parse_time_expr(expr: str) -> datetime` for PCP relative expressions (e.g. `"-6hours"`, `"-7days"`) and ISO-8601; no stdout writes (all logging to stderr)
- [X] T011 Implement `src/pmmcp/client.py`: async `PmproxyClient` wrapping `httpx.AsyncClient` with all methods from `data-model.md` (`series_sources`, `series_query`, `series_values`, `series_descs`, `series_instances`, `series_labels`, `search_text`, `search_suggest`, `pmapi_metric`, `pmapi_fetch`, `pmapi_indom`, `pmapi_children`, `pmapi_derive`, `_ensure_context`); full error hierarchy (`PmproxyError`, `PmproxyConnectionError`, `PmproxyNotFoundError`, `PmproxyTimeoutError`, `PmproxyAPIError`); HTTP status→exception mapping per `data-model.md` table; PMAPI context cache with `polltimeout=120s` and retry-on-403-expiry; `close()` method for lifespan cleanup
- [X] T012 Implement `src/pmmcp/server.py`: create `mcp = FastMCP("pmmcp")` instance; define `@asynccontextmanager` lifespan that creates shared `PmproxyClient(config)` and closes it on shutdown; expose client via `mcp.app_context`; define `mcp.run(transport="stdio")` entrypoint; import `src/pmmcp/tools` package to trigger `@mcp.tool` registration; **NO** `print()` or `sys.stdout.write()` calls anywhere in application code
- [X] T013 Implement `src/pmmcp/__main__.py`: `main()` parses `--pmproxy-url` (required) and `--timeout` (default 30.0) CLI args via `argparse`; constructs `PmproxyConfig`; calls `server.mcp.run(transport="stdio")`; supports `python -m pmmcp --pmproxy-url http://host:44322`
- [X] T014 [P] Create `src/pmmcp/tools/__init__.py` as empty file (side-effect imports added in T027, T031, T035 as tools are implemented)
- [X] T015 Create `tests/conftest.py`: `respx` mock fixtures for all pmproxy endpoints used across unit tests — `mock_series_sources`, `mock_series_query`, `mock_series_values`, `mock_pmapi_context`, `mock_pmapi_fetch`, `mock_pmapi_metric`, `mock_pmapi_indom`, `mock_pmapi_children`, `mock_pmapi_derive`, `mock_search_text`; shared `PmproxyConfig` test fixture; shared `PmproxyClient` test fixture using `respx.mock`
- [X] T016 Implement `tests/unit/test_utils.py`: unit tests for `resolve_interval()` covering all four auto-interval mappings, exact boundary conditions (3600s boundary, 86400s boundary, 604800s boundary), and pass-through of explicit interval strings; tests for `parse_time_expr()` covering PCP relative expressions (`"-1hour"`, `"-7days"`, `"-30min"`) and ISO-8601 absolute timestamps

**Checkpoint**: Foundation complete — `pytest tests/unit/test_utils.py` passes; all core modules exist and import cleanly

---

## Phase 3: User Story 1 — Interactive Performance Investigation (Priority: P1) 🎯 MVP

**Goal**: Enable the AI agent to retrieve live and historical performance data from pmproxy hosts, search for relevant metrics, and create derived metrics — the complete tool set needed to diagnose performance problems through natural language queries.

**Independent Test**: Connect pmmcp to a PCP-monitored host (or use respx mocks), ask "Why is the system slow right now?", and verify `pcp_get_hosts`, `pcp_fetch_live`, `pcp_fetch_timeseries`, `pcp_query_series`, `pcp_search`, and `pcp_derive_metric` all return well-structured paginated responses with correct Pydantic model output and consistent MCP error format on failure.

### Tests for User Story 1 *(Principle II — write first, verify FAIL, then implement)*

- [X] T017 [P] [US1] Write `tests/unit/test_hosts.py`: mock `GET /series/sources` via respx; assert `pcp_get_hosts()` returns `PaginatedResponse[Host]` with correct `source`, `hostnames`, `labels` fields; test glob `match` filter; test `limit`/`offset` pagination; test connection refused → MCP error response with `isError=true` and suggestion text
- [X] T018 [P] [US1] Write `tests/unit/test_live.py`: mock `GET /pmapi/context` + `GET /pmapi/fetch` via respx; assert `pcp_fetch_live()` returns timestamped `{name, instances: [{instance, value}]}` values; test `instances` filter; test expired-context 403 retry (context re-created on second attempt); test unknown metric → MCP not-found error
- [X] T019 [P] [US1] Write `tests/unit/test_timeseries.py`: mock `GET /series/query` + `GET /series/values` via respx; assert `pcp_fetch_timeseries()` resolves `"auto"` interval via `resolve_interval()` before calling pmproxy; assert paginated output grouped by metric/instance; test 500-point default limit enforcement; test `pcp_query_series()` with raw expression; test timeout → MCP timeout error with suggestion
- [X] T020 [P] [US1] Write `tests/unit/test_search.py`: mock `GET /search/text` via respx; assert `pcp_search()` returns `PaginatedResponse[SearchResult]` with `name`, `type`, `score`, `oneline`, `helptext`; test `type` filter param mapping (`"metric"`, `"indom"`, `"instance"`, `"all"`); test `limit`/`offset` pagination
- [X] T021 [P] [US1] Write `tests/unit/test_derived.py`: mock `GET /pmapi/derive` via respx; assert `pcp_derive_metric()` returns `{success: true, name, message}` on success; test derive failure (pmproxy error body) → MCP error with pmproxy message wrapped in context

### Implementation for User Story 1

- [X] T022 [P] [US1] Implement `src/pmmcp/tools/hosts.py`: `pcp_get_hosts(match="", limit=50, offset=0)` decorated with `@mcp.tool`; calls `client.series_sources(match)` → maps raw response to `Host` models → wraps in `PaginatedResponse`; catches all `PmproxyError` subtypes → returns consistent MCP error format per `contracts/mcp-tools.md` (category + description + suggestion)
- [X] T023 [P] [US1] Implement `src/pmmcp/tools/live.py`: `pcp_fetch_live(names, host="", instances=[])` decorated with `@mcp.tool`; calls `client._ensure_context(host)` then `client.pmapi_fetch(names, host)`; applies instance filter; returns `{timestamp, values: [{name, instances: [{instance, value}]}]}`; catches `PmproxyConnectionError`, `PmproxyTimeoutError`, `PmproxyNotFoundError`, `PmproxyAPIError` with categorised error messages
- [X] T024 [P] [US1] Implement `src/pmmcp/tools/timeseries.py`: `pcp_fetch_timeseries(names, start="-1hour", end="now", interval="auto", host="", instances=[], limit=500, offset=0, zone="UTC")` and `pcp_query_series(expr, start="-1hour", end="now", interval="auto", limit=500, offset=0)` both decorated with `@mcp.tool`; both call `resolve_interval()` before pmproxy; both call `client.series_query()` then `client.series_values()`; both enforce 500-point default limit; return `PaginatedResponse` of `{name, instance?, samples: [{timestamp, value}]}`
- [X] T025 [P] [US1] Implement `src/pmmcp/tools/search.py`: `pcp_search(query, type="all", limit=20, offset=0)` decorated with `@mcp.tool`; maps `type` to pmproxy `result_type` param; calls `client.search_text(query, result_type, limit, offset)`; returns `PaginatedResponse[SearchResult]`
- [X] T026 [P] [US1] Implement `src/pmmcp/tools/derived.py`: `pcp_derive_metric(name, expr, host="")` decorated with `@mcp.tool`; calls `client.pmapi_derive(name, expr, host)`; returns `{success: bool, name: str, message: str}`; catches derive failures → MCP error with raw pmproxy message wrapped in context description
- [X] T027 [US1] Update `src/pmmcp/tools/__init__.py`: add side-effect imports `from pmmcp.tools import hosts, live, timeseries, search, derived` to trigger `@mcp.tool` registration for all US1 tools
- [X] T028 [P] [US1] Create `agents/performance-investigator.md`: YAML frontmatter with `name: "performance-investigator"`, `description`, `mcpServers: [pmmcp]`, `tools: [pcp_get_hosts, pcp_discover_metrics, pcp_get_metric_info, pcp_fetch_live, pcp_fetch_timeseries, pcp_query_series, pcp_search, pcp_derive_metric]`; system prompt per `research.md` Decision 9a encoding: triage workflow (hosts→subsystem→specific metrics), hierarchical sampling strategy (coarse→fine drill-down), key metric families (CPU: `kernel.all.cpu.*`/`kernel.percpu.cpu.*`; Memory: `mem.util.*`; I/O: `disk.dev.*`; Network: `network.interface.*`; Process: `proc.*`), counter-vs-instant semantics, common saturation/bottleneck patterns, and structured output format (anomalies ranked by severity → supporting data → root cause → next steps)

**Checkpoint**: US1 complete — `pytest tests/unit/test_hosts.py tests/unit/test_live.py tests/unit/test_timeseries.py tests/unit/test_search.py tests/unit/test_derived.py` all pass; `pmmcp` starts via stdio and all 6 US1 tools appear in MCP tool listing

---

## Phase 4: User Story 2 — Metric Discovery and Exploration (Priority: P2)

**Goal**: Enable the AI agent to browse the PCP metric namespace tree and retrieve detailed metric metadata, giving users full discoverability of available metrics without prior PCP knowledge.

**Independent Test**: Connect to pmmcp and ask "What metrics are available on this host?" — verify `pcp_discover_metrics` returns a paginated categorised list with leaf/branch flags, and `pcp_get_metric_info` returns full help text, type, units, semantics, and instance domain members for a named metric. Results must be correctly structured without US1 tools (tools are independent).

### Tests for User Story 2 *(Principle II — write first, verify FAIL, then implement)*

- [X] T029 [P] [US2] Write `tests/unit/test_discovery.py`: mock `GET /pmapi/children` + `GET /search/text` + `GET /pmapi/metric` + `GET /pmapi/indom` via respx; assert `pcp_discover_metrics(prefix="kernel")` returns paginated `{name, oneline, leaf}` entries from namespace tree; assert `pcp_discover_metrics(search="cpu utilization")` calls search endpoint (not children); assert both `prefix` and `search` provided raises MCP validation error (mutually exclusive); assert `pcp_get_metric_info(names=["kernel.all.cpu.user"])` returns `Metric[]` with full `helptext`, `type`, `units`, `semantics`, `indom` fields; test unknown metric → MCP not-found error

### Implementation for User Story 2

- [X] T030 [US2] Implement `src/pmmcp/tools/discovery.py`: `pcp_discover_metrics(host="", prefix="", search="", limit=50, offset=0)` decorated with `@mcp.tool` — if `prefix`: calls `client.pmapi_children(prefix, host)` → returns paginated `{name, oneline, leaf: bool}` from `leaf`/`nonleaf` lists; if `search`: calls `client.search_text(search, limit=limit, offset=offset)` → maps to same format; if both empty: calls `pmapi_children("")` for root listing; raises MCP error if both `prefix` and `search` provided; `pcp_get_metric_info(names, host="")` decorated with `@mcp.tool` → calls `client.pmapi_metric(names, host)` then `client.pmapi_indom()` for each metric with non-null `indom` → returns `Metric[]` with all fields populated
- [X] T031 [US2] Update `src/pmmcp/tools/__init__.py`: append `from pmmcp.tools import discovery` to trigger `@mcp.tool` registration for `pcp_discover_metrics` and `pcp_get_metric_info`
- [X] T032 [P] [US2] Create `agents/metric-explorer.md`: YAML frontmatter with tool subset `[pcp_get_hosts, pcp_discover_metrics, pcp_get_metric_info, pcp_search]`; system prompt per `research.md` Decision 9a encoding: PCP namespace hierarchy (kernel.*, mem.*, disk.*, network.*, proc.*, hinv.*, pmda.*), metric semantics explanation (type/units/counter vs instant/indom in human terms), common metric categories and what questions each answers, exploration strategy (hosts→discover→info), and organised output format by category

**Checkpoint**: US2 complete — `pytest tests/unit/test_discovery.py` passes; `pcp_discover_metrics` and `pcp_get_metric_info` appear in MCP tool listing

---

## Phase 5: User Story 3 — Comparative Time-Period Analysis (Priority: P2)

**Goal**: Enable the AI agent to compare the same set of metrics across two user-specified time windows, returning statistical summaries (mean, min, max, p95, stddev) with computed deltas and significance flags for "good period vs bad period" analysis.

**Independent Test**: Provide two respx-mocked time windows with different metric distributions; verify `pcp_compare_windows` returns `WindowComparison[]` with correct `WindowStats` for each window and `DeltaStats.significant=true` for metrics that changed by more than 2 standard deviations; verify `significant=false` for identical windows.

### Tests for User Story 3 *(Principle II — write first, verify FAIL, then implement)*

- [X] T033 [P] [US3] Write `tests/unit/test_comparison.py`: mock two sequential `GET /series/values` calls (window A and window B) with different value distributions via respx; assert `pcp_compare_windows()` returns `WindowComparison[]` with correct `WindowStats` (mean, min, max, p95, stddev) for each window; assert `DeltaStats.significant=true` when `|mean_change| > 2 * window_a.stddev`; assert `DeltaStats.significant=false` for identical windows; assert `include_samples=true` includes raw data points alongside summary stats; assert `resolve_interval()` is applied to both windows using the same resolved interval

### Implementation for User Story 3

- [X] T034 [US3] Implement `src/pmmcp/tools/comparison.py`: `pcp_compare_windows(names, window_a_start, window_a_end, window_b_start, window_b_end, host="", instances=[], interval="auto", include_samples=false)` decorated with `@mcp.tool`; resolves interval once via `resolve_interval(window_a_start, window_a_end, interval)` and applies to both windows; calls `client.series_values()` twice; computes `WindowStats` (mean, min, max, p95 via sorted percentile, stddev) for each window; computes `DeltaStats` (mean_change, mean_change_pct, stddev_change, significant = `|mean_change| > 2 * window_a.stddev`); returns `WindowComparison[]`
- [X] T035 [US3] Update `src/pmmcp/tools/__init__.py`: append `from pmmcp.tools import comparison` to trigger `@mcp.tool` registration for `pcp_compare_windows`
- [X] T036 [P] [US3] Create `agents/performance-comparator.md`: YAML frontmatter with tool subset `[pcp_get_hosts, pcp_discover_metrics, pcp_fetch_timeseries, pcp_compare_windows, pcp_search, pcp_derive_metric]`; system prompt per `research.md` Decision 9a encoding: comparison methodology (`delta.significant == true` focus), hierarchical approach (broad key metrics first then drill into significant subsystems), statistical interpretation in practical terms (50% CPU increase at 2% baseline is different from 50% at 80% baseline), natural language time period parsing, and ranked output table format (metrics sorted by significance with before/after stats and plain-language interpretation)

**Checkpoint**: US3 complete — `pytest tests/unit/test_comparison.py` passes; `pcp_compare_windows` appears in MCP tool listing; all 9 tools from `contracts/mcp-tools.md` are now registered

---

## Phase 6: User Story 4 — Periodic Summary Reports (Priority: P3)

**Goal**: Enable the AI agent to generate structured performance summary reports over a defined time period. US4 requires **no new MCP tools** — all needed tools (`pcp_get_hosts`, `pcp_fetch_timeseries`, `pcp_compare_windows`, `pcp_search`, `pcp_derive_metric`) are implemented in US1–US3. The sole deliverable is the performance-reporter subagent definition.

**Independent Test**: With all US1–US3 tools available, use the performance-reporter subagent to ask "Give me a monthly summary of all services" — verify the agent produces a structured Markdown report with executive summary, per-host KPI table with trend indicators (improving/stable/degrading), and notable anomaly flags.

- [X] T037 [P] [US4] Create `agents/performance-reporter.md`: YAML frontmatter with `name: "performance-reporter"`, tool subset `[pcp_get_hosts, pcp_fetch_timeseries, pcp_compare_windows, pcp_search, pcp_derive_metric]`; system prompt per `research.md` Decision 9a encoding: report structure (executive summary → per-host KPI breakdown → trend analysis → recommendations), default KPIs per subsystem (CPU: user+sys utilisation; Memory: used/total; Disk: I/O await; Network: throughput; Load: load average), trend classification using linear trend on time-series data (improving/stable/degrading), anomaly flagging (step changes in mean, sustained high-utilisation, capacity approaching limits), hierarchical sampling for weekly/monthly windows (use hourly intervals for full period — do not auto-drill), and Markdown output format

**Checkpoint**: US4 complete — all 4 subagent `.md` files exist in `agents/`

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Contract testing, integration tests, coverage validation, packaging completeness

- [X] T038 [P] Write `tests/contract/test_mcp_schemas.py`: use MCP in-memory `Client(mcp)` to call each of the 9 tools with valid inputs; assert returned JSON schemas match Pydantic model definitions; verify all 9 tools appear in MCP tool listing (`pcp_get_hosts`, `pcp_discover_metrics`, `pcp_get_metric_info`, `pcp_fetch_live`, `pcp_fetch_timeseries`, `pcp_query_series`, `pcp_compare_windows`, `pcp_search`, `pcp_derive_metric`); test error response format (`isError=true`, text with category + description + suggestion) matches `contracts/mcp-tools.md` error contract for all 5 error categories
- [X] T039 Write `tests/integration/test_integration.py`: full end-to-end scenarios for US1–US4 using live pmproxy; auto-skip entire module with `pytest.skip("PMPROXY_URL not set", allow_module_level=True)` when env var absent; cover: host discovery (SC-004: <10s), live fetch (SC-001: <5s), 7-day timeseries with auto-interval (SC-002: <15s), metric search, two-window comparison, derived metric creation; assert SLA timings using `time.monotonic()`
- [X] T040 [P] Verify `ruff check src/ tests/` reports zero violations; apply `ruff format src/ tests/` to ensure consistent style; fix any remaining lint issues (unused imports, complexity violations, non-snake-case names)
- [X] T041 Run `pytest --cov=pmmcp --cov-report=term-missing --cov-fail-under=80`; identify and add targeted tests to `tests/unit/` for any uncovered branches in `client.py` (error paths, context retry), `utils.py` (boundary cases), and tool handlers (all `PmproxyError` subtypes)
- [X] T042 [P] Write `README.md`: project overview and value proposition, prerequisites (PCP + pmproxy with Valkey/Redis backend for time-series), installation (Docker/uvx/source), Claude Code MCP configuration JSON snippets for all three modes, subagent installation (`cp agents/*.md ~/.claude/agents/`), example natural language queries, and development setup commands per `quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately; T001→T002 sequential; T003–T006 parallel after T002
- **Phase 2 (Foundational)**: After Phase 1; T007 first; T008+T010+T014 parallel; T009 after T007; T011 after T008+T009; T012 after T011; T013 after T012; T015 after T009; T016 after T015; **BLOCKS all user story phases**
- **Phase 3 (US1)**: After Phase 2; T017–T021 tests first (all parallel); T022–T026 implementations (all parallel, after tests confirmed failing); T027 sequential (updates `__init__.py`); T028 parallel
- **Phase 4 (US2)**: After Phase 2; independent of US1 (different files); T029 test first; T030 implementation; T031 sequential; T032 parallel
- **Phase 5 (US3)**: After Phase 2; independent of US1/US2 (different files); T033 test first; T034 implementation; T035 sequential; T036 parallel
- **Phase 6 (US4)**: After Phase 3+5 completion (reporter references their tools in frontmatter); T037 standalone
- **Phase 7 (Polish)**: After all user story phases; T038+T040+T042 parallel; T039 after T038; T041 after T039

### User Story Dependencies

- **US1 (P1)**: After Phase 2 — no story dependencies. **MVP.**
- **US2 (P2)**: After Phase 2 — independent of US1; different tool files; can proceed in parallel with US1
- **US3 (P2)**: After Phase 2 — uses `resolve_interval` (foundational); independent of US1/US2; can proceed in parallel
- **US4 (P3)**: After US1+US3 complete (needs those tools operational); minimal work (one subagent file)

### Within Each Phase (TDD Order)

1. Write tests → verify they FAIL
2. Implement → verify tests PASS
3. Models before services, services before tool handlers
4. Tool handlers in parallel (different files, shared client via context)
5. `tools/__init__.py` updates sequential (one file, one import appended per story: T027 → T031 → T035)

### Parallel Opportunities

- **Phase 1**: T003, T004, T005, T006 all parallel after T001+T002
- **Phase 2**: T008, T010, T014 parallel after T007; T015 after T009; T016 after T015; T009→T011→T012→T013 sequential chain
- **Phase 3**: T017–T021 all parallel (5 different test files); T022–T026 all parallel (5 different tool files)
- **Phase 4**: T029, T032 parallel; T030→T031 sequential
- **Phase 5**: T033, T036 parallel; T034→T035 sequential
- **Phase 7**: T038, T040, T042 parallel; T039 after T038; T041 after T039
- **Cross-story**: US1, US2, US3 phases can run in parallel with separate developers once Phase 2 is complete

---

## Parallel Example: Phase 3 (User Story 1)

```bash
# Step 1 — Write all US1 tests in parallel (TDD: confirm they FAIL before implementing):
Task: "Write tests/unit/test_hosts.py"       # T017
Task: "Write tests/unit/test_live.py"        # T018
Task: "Write tests/unit/test_timeseries.py"  # T019
Task: "Write tests/unit/test_search.py"      # T020
Task: "Write tests/unit/test_derived.py"     # T021

# Step 2 — Implement all US1 tool modules in parallel (tests now failing):
Task: "Implement src/pmmcp/tools/hosts.py"      # T022
Task: "Implement src/pmmcp/tools/live.py"       # T023
Task: "Implement src/pmmcp/tools/timeseries.py" # T024
Task: "Implement src/pmmcp/tools/search.py"     # T025
Task: "Implement src/pmmcp/tools/derived.py"    # T026

# Step 3 — Sequential wiring:
Task: "Update src/pmmcp/tools/__init__.py with US1 imports"  # T027
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T006)
2. Complete Phase 2: Foundational (T007–T016) — CRITICAL, blocks everything
3. Complete Phase 3: User Story 1 (T017–T028)
4. **STOP and VALIDATE**: `pytest tests/unit/test_hosts.py tests/unit/test_live.py tests/unit/test_timeseries.py tests/unit/test_search.py tests/unit/test_derived.py` — all pass; start server via `python -m pmmcp --pmproxy-url http://host:44322`, connect Claude Code, verify "What hosts are monitored?" returns data
5. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. US1 (P1) → test independently → **MVP: interactive investigation works**
3. US2 (P2) → test independently → metric discovery works
4. US3 (P2) → test independently → time-period comparison works
5. US4 (P3) → subagent only → performance reporter subagent available
6. Polish → contract tests, integration tests, coverage gate, CI green

### Parallel Team Strategy

After Phase 2 completes:

- **Developer A**: Phase 3 (US1) — `hosts.py`, `live.py`, `timeseries.py`, `search.py`, `derived.py`
- **Developer B**: Phase 4 (US2) — `discovery.py` (different files, no conflicts)
- **Developer C**: Phase 5 (US3) — `comparison.py` (different files, no conflicts)

Merge `tools/__init__.py` updates in priority order (US1 → US2 → US3) to avoid conflicts.

---

## Task Count Summary

| Phase | Tasks | Parallel opportunities |
|-------|-------|----------------------|
| Phase 1: Setup | T001–T006 (6) | T003–T006 (4 parallel) |
| Phase 2: Foundational | T007–T016 (10) | T008, T010, T014 parallel |
| Phase 3: US1 (P1) | T017–T028 (12) | T017–T021 parallel; T022–T026 parallel |
| Phase 4: US2 (P2) | T029–T032 (4) | T029, T032 parallel |
| Phase 5: US3 (P2) | T033–T036 (4) | T033, T036 parallel |
| Phase 6: US4 (P3) | T037 (1) | Standalone |
| Phase 7: Polish | T038–T042 (5) | T038, T040, T042 parallel |
| **Total** | **42 tasks** | |

---

## Notes

- **Never write to stdout** from application code — breaks stdio JSON-RPC framing. Use `logging` to stderr only. This applies to all modules in `src/pmmcp/`.
- `tools/__init__.py` updates (T027 → T031 → T035) are sequential — each appends one import line; preserve existing imports.
- The 9 MCP tools map to 7 tool modules: `hosts.py`→1 tool, `discovery.py`→2, `live.py`→1, `timeseries.py`→2, `comparison.py`→1, `search.py`→1, `derived.py`→1.
- PMAPI context cache lives in the `PmproxyClient` instance; shared across tool calls via FastMCP lifespan app context.
- Integration tests in `tests/integration/` auto-skip when `PMPROXY_URL` env var is absent — CI runs without a real pmproxy.
- [P] tasks = operate on different files with no dependency on incomplete tasks in the same phase.
- [Story] label maps each task to a specific user story for traceability and independent delivery.
- Commit after each logical group (e.g., after all US1 tests pass, after each `__init__.py` update).
- Stop at each **Checkpoint** to validate the story independently before moving to the next phase.
