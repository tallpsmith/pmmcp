# Research: PCP MCP Service (pmmcp)

**Feature**: 001-pcp-mcp-service
**Date**: 2026-02-21

## Decision 1: Language and Runtime

**Decision**: Python 3.11+

**Rationale**:
- PCP has a strong Python heritage — the project's tooling, PMDAs, and community contributions are predominantly Python-based. Choosing Python ensures pmmcp is accessible and contributable by PCP maintainers and the broader PCP developer community.
- The official MCP Python SDK (`mcp`) is at feature parity with the TypeScript SDK, supporting stdio, SSE, and Streamable HTTP transports.
- Python's `FastMCP` interface provides decorator-based tool registration (`@mcp.tool()`) with automatic schema generation from type hints and Pydantic models — minimal boilerplate for a REST API wrapper.
- Python's async/await via `asyncio` is well-suited for concurrent HTTP calls to pmproxy.
- Python 3.11+ provides significant performance improvements and better error messages over earlier versions.

**Alternatives considered**:
- **TypeScript** (`@modelcontextprotocol/sdk`): Anthropic's reference implementation; slightly more mature ecosystem; better compile-time type safety. Rejected because PCP maintainer familiarity and community contribution potential outweigh the TypeScript SDK's marginal advantages. The Python SDK is fully capable for this use case.
- **Go** (official SDK): Single static binary, no runtime dependency. Rejected because: (a) less mature MCP ecosystem, (b) PCP community is not Go-centric, (c) Go's error handling verbosity would slow development.

## Decision 2: MCP SDK

**Decision**: `mcp` (official MCP Python SDK, v1.x) using the `FastMCP` high-level interface

**Rationale**:
- `FastMCP` is now part of the official `mcp` package (merged in v1.x) — not a separate dependency.
- Decorator-based tool registration generates MCP schemas directly from Python type hints and docstrings, reducing duplication between code and contract definitions.
- Supports both stdio and Streamable HTTP transports via `mcp.run(transport="stdio")` or ASGI integration.
- Pydantic v2 is used internally for validation, aligning with our data model approach.

**Alternatives considered**:
- Raw `mcp` low-level API: More control but significantly more boilerplate. FastMCP is the recommended high-level interface from the SDK authors. Rejected per Principle V (Simplicity).

## Decision 3: HTTP Client for pmproxy

**Decision**: `httpx` (async HTTP client)

**Rationale**:
- Modern async Python HTTP client with a clean API similar to `requests` but with native async/await support.
- Built-in timeout handling, connection pooling, and retry support.
- Well-tested and widely adopted in the Python async ecosystem.
- `httpx` is the recommended HTTP client in the MCP Python SDK documentation.

**Alternatives considered**:
- **aiohttp**: Mature async client but more verbose API and heavier dependency tree. httpx is simpler for this use case.
- **requests**: Synchronous only. Would require threading or process pools for concurrent pmproxy calls. Rejected because the MCP SDK is async-native.
- **urllib3 / built-in urllib**: Too low-level for comfortable use. httpx provides the right abstraction level.

## Decision 4: Testing Framework

**Decision**: pytest with pytest-asyncio

**Rationale**:
- pytest is the de facto standard for Python testing, with rich plugin ecosystem.
- pytest-asyncio provides native support for testing async functions (the MCP SDK and httpx are both async).
- pytest-cov for coverage reporting, integrated into CI.
- Fixture-based test setup aligns well with creating mock pmproxy responses.

**Alternatives considered**:
- **unittest**: Standard library but more verbose. pytest's fixture system and assertion introspection are significantly more productive for TDD.

## Decision 5: HTTP Mocking for Tests

**Decision**: `respx` (httpx mock library)

**Rationale**:
- Purpose-built for mocking `httpx` requests — intercepts at the transport layer, testing the full HTTP client path.
- Declarative route matching patterns align well with pmproxy's REST API structure.
- Pytest plugin integration via `@respx.mock` decorator.
- Actively maintained and designed specifically for the httpx client we're using.

**Alternatives considered**:
- **responses**: Only works with `requests`, not `httpx`. Incompatible.
- **vcrpy / pytest-recording**: Records and replays HTTP interactions. Useful for integration tests but adds complexity for unit tests. May be added later for integration testing against real pmproxy.
- **aioresponses**: For `aiohttp`, not `httpx`. Incompatible.

## Decision 6: Linting and Formatting

**Decision**: Ruff (linter + formatter)

**Rationale**:
- Single tool replaces both flake8 (linting) and black (formatting).
- Extremely fast — written in Rust, runs in milliseconds even on large codebases.
- Supports all relevant lint rules (pyflakes, pycodestyle, isort, pydocstyle, etc.).
- Growing adoption in the Python ecosystem; well-maintained.
- Constitution Principle I requires linting and formatting enforcement.

**Alternatives considered**:
- **flake8 + black + isort**: Three separate tools to install and configure. Ruff replaces all three with a single dependency and config section.

## Decision 7: MCP Tool Set (Scope)

**Decision**: 9 tools in initial build

**Tools included**:
1. `pcp_get_hosts` — list monitored hosts
2. `pcp_discover_metrics` — browse/search metric namespaces
3. `pcp_get_metric_info` — detailed metric metadata
4. `pcp_fetch_live` — real-time current values
5. `pcp_fetch_timeseries` — historical time-series data
6. `pcp_query_series` — raw series query expression
7. `pcp_compare_windows` — two-window comparison with summary stats
8. `pcp_search` — full-text search across metrics
9. `pcp_derive_metric` — create computed metrics on-the-fly

**Tools deferred**:
- `pcp_get_openmetrics` — bulk Prometheus-format export. Not needed when structured tools exist.
- `pcp_store_metric` — write access is risky and not required by any in-scope user story.
- `pcp_load_series` — archive loading is an admin task, not an analysis task.

**Rationale**: 9 tools provide complete coverage of US1-US4 without unnecessary complexity. Per Principle V, deferred tools can be added when a concrete need arises.

## Decision 8: Auto-Interval Strategy

**Decision**: Time-series tools default to `"auto"` interval, which selects granularity based on window size.

**Mapping**:
| Window Duration | Auto Interval |
|----------------|---------------|
| ≤ 1 hour       | 15 seconds    |
| ≤ 24 hours     | 5 minutes     |
| ≤ 7 days       | 1 hour        |
| > 7 days       | 6 hours       |

**Rationale**: Implements the hierarchical sampling strategy from FR-008 and the clarification session. The AI agent starts coarse, identifies patterns, then drills down with explicit finer intervals. This prevents context window exhaustion on large time ranges.

## Decision 9: Subagent Definition Format

**Decision**: Markdown files with YAML frontmatter, stored in `agents/` at repository root.

**Rationale**:
- Claude Code supports custom subagent definitions as `.md` files in `.claude/agents/` (project) or `~/.claude/agents/` (user).
- Storing them in `agents/` at repo root lets users copy them to their own `.claude/agents/` directory.
- The frontmatter supports `mcpServers` to reference the pmmcp MCP server.
- 4 subagent definitions: performance-investigator, metric-explorer, performance-comparator, performance-reporter.

## Decision 9a: Subagent Content Specifications

**Context**: Decision 9 established the format (markdown + YAML frontmatter in `agents/`). This section defines the actual content for each of the 4 subagent definitions.

### Frontmatter Structure (all agents)

```yaml
---
name: "<agent-display-name>"
description: "<one-line purpose>"
mcpServers:
  - pmmcp
tools:
  - pcp_get_hosts
  # ... agent-specific tool subset
---
```

### Agent 1: performance-investigator

**File**: `agents/performance-investigator.md`
**Purpose**: Diagnose performance problems from natural language descriptions (US1).
**Tools used**: `pcp_get_hosts`, `pcp_discover_metrics`, `pcp_get_metric_info`, `pcp_fetch_live`, `pcp_fetch_timeseries`, `pcp_query_series`, `pcp_search`, `pcp_derive_metric`

**Domain knowledge to encode:**
- **Triage workflow**: Start broad → narrow down. First identify which hosts are affected, then which subsystem (CPU, memory, I/O, network), then which specific metrics are anomalous.
- **Hierarchical sampling**: When investigating a problem, always start with coarse intervals (hourly for past week) to identify when the problem started, then drill into that window at finer intervals (5min, then 15s).
- **Key metric families** and what they indicate:
  - CPU: `kernel.all.cpu.*`, `kernel.percpu.cpu.*` — user vs system vs iowait vs steal
  - Memory: `mem.util.*`, `mem.vmstat.*` — free, available, swap, page faults
  - I/O: `disk.dev.*`, `disk.all.*` — read/write IOPS, latency, throughput, queue depth
  - Network: `network.interface.*` — packets, errors, drops, bandwidth
  - Process: `proc.*`, `hotproc.*` — per-process resource consumption
- **Counter vs instant semantics**: Counters must be rate-converted (delta/interval) before analysis. The agent should request raw counter values and compute rates, or use derived metrics.
- **Common patterns**: CPU saturation (high runnable queue), memory pressure (swap activity + page reclaims), I/O bottleneck (high await + low throughput), network saturation (drops/errors).
- **Output format**: Structured summary with: (1) identified anomalies ranked by severity, (2) supporting metric data, (3) likely root cause, (4) recommended next steps.

### Agent 2: metric-explorer

**File**: `agents/metric-explorer.md`
**Purpose**: Discover and explain available metrics and infrastructure (US2).
**Tools used**: `pcp_get_hosts`, `pcp_discover_metrics`, `pcp_get_metric_info`, `pcp_search`

**Domain knowledge to encode:**
- **PCP namespace hierarchy**: Top-level namespaces and what they contain (`kernel.*`, `mem.*`, `disk.*`, `network.*`, `proc.*`, `hinv.*` hardware inventory, `pmda.*` agent-specific).
- **Metric semantics explanation**: How to interpret type, units, semantics (counter/instant/discrete), and instance domains in human terms.
- **Common metric categories**: CPU metrics, memory metrics, disk metrics, network metrics, filesystem metrics, process metrics, and what questions each category can answer.
- **Exploration strategy**: Start with `pcp_get_hosts` to show available infrastructure, then `pcp_discover_metrics` with prefix browsing for broad overview, then `pcp_get_metric_info` for detail on specific metrics.
- **Output format**: Organised by category with human-readable descriptions. When explaining a specific metric, include: what it measures, typical units, whether it's a counter or gauge, what instance domain it has, and when/why you'd look at it.

### Agent 3: performance-comparator

**File**: `agents/performance-comparator.md`
**Purpose**: Compare performance between two time periods (US3).
**Tools used**: `pcp_get_hosts`, `pcp_discover_metrics`, `pcp_fetch_timeseries`, `pcp_compare_windows`, `pcp_search`, `pcp_derive_metric`

**Domain knowledge to encode:**
- **Comparison methodology**: Use `pcp_compare_windows` for statistical comparison. Focus on metrics where `delta.significant == true` (> 2 standard deviations).
- **Hierarchical approach**: First compare with a broad set of key metrics (CPU, memory, I/O, network aggregates). Then drill into the subsystems that show significant changes.
- **Statistical interpretation**: Explain what mean change, stddev change, and p95 change indicate in practical terms. A 50% increase in mean CPU doesn't matter if baseline was 2% — focus on the actual utilisation levels.
- **Time window parsing**: Help users specify time periods from natural language ("last week", "yesterday morning", "the deployment on Tuesday").
- **Output format**: Table of metrics ranked by significance, with before/after stats, percentage change, and plain-language interpretation of what changed and potential causes.

### Agent 4: performance-reporter

**File**: `agents/performance-reporter.md`
**Purpose**: Generate structured performance summary reports (US4).
**Tools used**: `pcp_get_hosts`, `pcp_fetch_timeseries`, `pcp_compare_windows`, `pcp_search`, `pcp_derive_metric`

**Domain knowledge to encode:**
- **Report structure**: Executive summary → per-host/service breakdown → trend analysis → recommendations.
- **KPI selection**: Default KPIs per subsystem: CPU utilisation (user+sys), memory utilisation (used/total), disk I/O latency (await), network throughput, load average.
- **Trend detection**: Use `pcp_fetch_timeseries` with coarse intervals over the report period. Classify each KPI as improving/stable/degrading based on linear trend in the data.
- **Anomaly flagging**: Identify sudden changes (step changes in mean), sustained high-utilisation periods, and capacity approaching limits.
- **Hierarchical sampling**: For weekly/monthly reports, use hourly intervals for the full period. Flag interesting periods for potential drill-down but don't drill automatically (the report should be concise).
- **Output format**: Markdown report with: (1) executive summary (2-3 sentences), (2) per-host KPI table with trend indicators, (3) notable events/anomalies with approximate timestamps, (4) recommendations.

## Decision 10: Project Packaging

**Decision**: Python package with `pyproject.toml` and `[project.scripts]` entry point, plus a Docker container image published to GHCR.

**Rationale**:

### Python Package (primary)
- Users configure Claude Code MCP servers with a command. For pmmcp: `uvx pmmcp --pmproxy-url http://host:44322` or `python -m pmmcp --pmproxy-url http://host:44322`.
- `pyproject.toml` is the modern Python packaging standard (PEP 621).
- A `[project.scripts]` entry creates the `pmmcp` command: `pmmcp = "pmmcp.__main__:main"`.
- Future HTTP transport would add an alternative `pmmcp serve` subcommand.
- The package can be published to PyPI for `pip install pmmcp` / `uvx pmmcp`.

### Docker Container (complementary)
- Eliminates the Python runtime dependency entirely — users who don't have (or don't want) Python can run pmmcp with a single `docker run` command.
- Minimal configuration: the pmproxy URL is passed as an environment variable (`PMPROXY_URL`) or command-line argument.
- Multi-stage Dockerfile: build stage installs dependencies, runtime stage uses a slim Python base for minimal image size.
- Published to GitHub Container Registry (GHCR) via CI for easy `docker pull ghcr.io/<org>/pmmcp`.
- Claude Code MCP configuration uses `docker` as the command with appropriate args.
- The same container can serve both stdio transport (default, for local use) and future Streamable HTTP transport (`pmmcp serve` subcommand).

**Docker MCP configuration** (stdio transport):
```json
{
  "mcpServers": {
    "pmmcp": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "ghcr.io/<org>/pmmcp", "--pmproxy-url", "http://your-pmproxy-host:44322"]
    }
  }
}
```

Note: The `-i` flag (interactive / keep stdin open) is required for stdio transport. The `--rm` flag auto-removes the container on exit. No `-t` (tty) flag — MCP stdio communication is not terminal-based.

**Alternatives considered**:
- **setup.py / setup.cfg**: Legacy packaging. pyproject.toml is the modern standard per PEP 621.
- **Docker-only (no Python package)**: Would force all users through Docker, penalising those who already have Python and prefer `uvx`. Both channels serve different audiences.
- **Snap / Flatpak / Homebrew**: Platform-specific distribution. Docker is cross-platform and already ubiquitous in the sysadmin/SRE audience that uses PCP.
