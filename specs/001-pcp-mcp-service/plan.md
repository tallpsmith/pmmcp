# Implementation Plan: PCP MCP Service (pmmcp)

**Branch**: `001-pcp-mcp-service` | **Date**: 2026-02-21 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-pcp-mcp-service/spec.md`

## Summary

Build a Python-based MCP server (`pmmcp`) that wraps the pmproxy REST API (PMWEBAPI), exposing 9 MCP tools for live metric queries, historical time-series analysis, metric discovery, full-text search, time-period comparison, and derived metric creation. The server uses FastMCP (official `mcp` Python SDK v1.x) with stdio transport for the initial build, with a clean transport/handler separation to support future Streamable HTTP without code changes. Four companion subagent definitions encode PCP performance domain knowledge and the hierarchical sampling strategy required by FR-008.

---

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: `mcp[cli]` ≥1.2.0 (FastMCP), `pydantic` v2.x + `pydantic-settings`, `httpx` ≥0.27; dev: `pytest`, `pytest-asyncio`, `respx`, `ruff`
**Storage**: N/A (stateless MCP server; pmproxy provides all data via REST API)
**Testing**: pytest + pytest-asyncio; `respx` for httpx transport-level mocking; in-memory `Client(mcp)` for MCP tool integration tests
**Target Platform**: Linux/macOS — subprocess launched by Claude Code via stdio (initial); future: server process with Streamable HTTP transport
**Project Type**: Single Python package
**Performance Goals**:
- Live queries: p95 < 5 s end-to-end (SC-001)
- Historical 7-day window: p95 < 15 s (SC-002)
- Metric discovery: p95 < 10 s (SC-004)
**Constraints**:
- Default max 500 data points per time-series tool call (configurable, enforced via `samples` parameter)
- Single pmproxy endpoint; no authentication in initial build (placeholder fields reserved)
- Never write to stdout from application code (breaks stdio JSON-RPC framing)
**Scale/Scope**: 50+ simultaneous hosts via single pmproxy (SC-007); ~9 MCP tools; 4 subagent definitions

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes / Justification |
|-----------|--------|----------------------|
| I. Code Quality — linting enforced, single-responsibility, complexity ≤ 10, peer review | **PASS** | `ruff` enforces lint + format in CI; each `tools/*.py` module handles one functional area; tool handlers are dispatch wrappers (low cyclomatic complexity); PR review required per governance |
| II. Testing Standards — TDD cycle, ≥ 80% unit coverage, contract tests on interface changes | **PASS** | pytest + pytest-asyncio; `respx` mocks pmproxy at HTTP transport layer; `Client(mcp)` in-memory MCP tests; contract tests in `tests/contract/` verify tool schemas match Pydantic models; coverage target ≥ 80% enforced in CI |
| III. UX Consistency — design system adherence, WCAG 2.1 AA, actionable error messages | **PASS / N/A** | No UI components; tool error responses follow a consistent structure (error category + description + suggestion) per FR-009; tool descriptions and parameter docs are LLM-readable and consistent across all 9 tools |
| IV. Performance — latency SLA defined, performance budget in CI, profiling before optimization | **PASS** | SLAs defined in spec (SC-001: <5s live, SC-002: <15s historical, SC-004: <10s discovery); auto-interval selection (research.md Decision 8) and pagination (FR-007) keep data volume in budget; performance regression tests cover SLA paths |
| V. Simplicity — YAGNI posture, no speculative abstractions, complexity justified below | **PASS** | 9 tools (not over-engineered); module separation is functional (required by spec scope), not speculative; subagents explicitly required by FR-008; no infrastructure beyond a single Python package + Docker image; transport abstraction is zero-cost (FastMCP handles it) |

**Post-Phase-1 re-check**: PASS maintained. Data model (data-model.md) introduces `PaginatedResponse[T]`, `WindowComparison`, `ComparisonResult` — all required by FR-007 and FR-011; no speculative additions.

---

## Project Structure

### Documentation (this feature)

```text
specs/001-pcp-mcp-service/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/
│   ├── mcp-tools.md     # MCP tool schemas (input/output contracts)
│   └── pmproxy-api.md   # pmproxy REST API wire formats (for implementors)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/pmmcp/
├── __init__.py          # Package version
├── __main__.py          # CLI entrypoint: python -m pmmcp --pmproxy-url ...
├── server.py            # FastMCP instance, lifespan (shared httpx.AsyncClient),
│                        # transport entrypoint (mcp.run)
├── config.py            # PmproxyConfig (pydantic-settings, env prefix PMPROXY_)
├── client.py            # PmproxyClient: httpx wrapper; PmproxyError hierarchy
├── models.py            # Pydantic models: Host, Metric, Instance, MetricValue,
│                        # TimeWindow, WindowComparison, SearchResult, PaginatedResponse
├── utils.py             # resolve_interval() (auto-interval logic), time parsing
└── tools/
    ├── __init__.py      # Side-effect imports to trigger @mcp.tool registration
    ├── hosts.py         # pcp_get_hosts
    ├── discovery.py     # pcp_discover_metrics, pcp_get_metric_info
    ├── live.py          # pcp_fetch_live
    ├── timeseries.py    # pcp_fetch_timeseries, pcp_query_series
    ├── comparison.py    # pcp_compare_windows
    ├── search.py        # pcp_search
    └── derived.py       # pcp_derive_metric

tests/
├── conftest.py          # respx fixtures for all pmproxy mock responses
├── unit/
│   ├── test_hosts.py
│   ├── test_discovery.py
│   ├── test_live.py
│   ├── test_timeseries.py
│   ├── test_comparison.py
│   ├── test_search.py
│   ├── test_derived.py
│   └── test_utils.py    # resolve_interval() and time-parsing unit tests
├── integration/         # Require PMPROXY_URL env var; auto-skipped without it
│   └── test_integration.py
└── contract/
    └── test_mcp_schemas.py  # Verify FastMCP-generated JSON schemas match Pydantic models

agents/                  # Subagent definitions (version-controlled; copy to ~/.claude/agents/)
├── performance-investigator.md
├── metric-explorer.md
├── performance-comparator.md
└── performance-reporter.md

Dockerfile               # Multi-stage: build (uv install) → runtime (slim Python)
pyproject.toml           # PEP 621; [project.scripts] pmmcp = "pmmcp.__main__:main"
.mcp.json.example        # Example Claude Code MCP configuration
```

**Structure Decision**: Single Python package (`src/pmmcp/`) with `tools/` sub-package. Chosen because pmmcp is a single-purpose service with no separate backend/frontend split. The `tools/` sub-package groups tool handlers by functional area (matching the 9-tool design in contracts/mcp-tools.md) while sharing `PmproxyClient` and `PmproxyConfig` via the FastMCP lifespan context.

---

## Complexity Tracking

> No constitution violations to justify. All architectural decisions are either directly required by the specification or follow from YAGNI:

| Decision | Why Needed | Simpler Alternative Rejected Because |
|----------|------------|-------------------------------------|
| `tools/` sub-package with 7 modules | FR-001–FR-012 require 9 distinct tool categories with different pmproxy API surfaces (live vs. series vs. search) | Single `tools.py` file would exceed 500 lines and violate single-responsibility (Principle I) |
| `client.py` abstraction layer | All 9 tools share pmproxy connection; context caching (PMAPI) and error normalisation are reused | Inline httpx calls in each tool would duplicate connection/error logic 9×; abstraction appears 9+ times (rule of 3 satisfied) |
| `agents/` directory with 4 subagents | FR-008 explicitly requires companion subagent definitions encoding domain knowledge and hierarchical sampling | N/A — explicitly required |
| Docker image (complementary to Python package) | PCP administrators often do not have Python in their environment; Docker eliminates runtime dependency | Python-only would exclude a significant portion of the target audience |
