# pmmcp — PCP MCP Service

An [MCP](https://modelcontextprotocol.io) server that exposes [Performance Co-Pilot (PCP)](https://pcp.io) metrics to AI agents via [pmproxy](https://man7.org/linux/man-pages/man1/pmproxy.1.html). Enables Claude and other LLMs to query live and historical performance data from any PCP-monitored host.

## What It Does

pmmcp gives AI agents 9 MCP tools and 4 MCP prompt templates for performance investigation:

| Tool | Description |
|------|-------------|
| `pcp_get_hosts` | List monitored hosts with labels and metadata |
| `pcp_discover_metrics` | Browse the metric namespace tree or search by keyword |
| `pcp_get_metric_info` | Get full metadata for one or more metrics |
| `pcp_fetch_live` | Fetch current metric values from a live host |
| `pcp_fetch_timeseries` | Fetch historical time-series data with auto-interval resolution |
| `pcp_query_series` | Execute raw PCP series query expressions |
| `pcp_compare_windows` | Statistical comparison of two time windows |
| `pcp_search` | Full-text search across metric names and help text |
| `pcp_derive_metric` | Create computed metrics on the fly |

## Prerequisites

- **PCP** installed and running on at least one monitored host
- **pmproxy** running and accessible (default port: 44322)
  - For time-series features (`pcp_fetch_timeseries`, `pcp_query_series`, `pcp_compare_windows`): pmproxy must be configured with a Valkey/Redis backend
- **Claude Code** (or another MCP client)
- **One of**: Python 3.11+ or Docker

## Installation

> **Note:** Docker image and PyPI package publishing are not yet available. Install from source for now.

### From Source

```bash
git clone <repository-url>
cd pmmcp
uv sync
```

## Configure Claude Code

Add pmmcp to `.mcp.json` in your project root (or `~/.claude/mcp.json` for global config).

### Python (installed from source)

```json
{
  "mcpServers": {
    "pmmcp": {
      "command": "python",
      "args": ["-m", "pmmcp", "--pmproxy-url", "http://your-pmproxy-host:44322"]
    }
  }
}
```

### Optional: custom timeout

Add `"--timeout", "60"` to the `args` array to increase the HTTP timeout (default: 30 seconds).

## Prompts

pmmcp exposes four MCP prompt templates that seed an AI conversation with an expert
investigation workflow. Invoke any prompt from your MCP client to get step-by-step
guidance without reading external documentation.

| Prompt | Required args | Optional args | Workflow |
|--------|--------------|---------------|---------|
| `investigate_subsystem` | `subsystem` | `host`, `timerange`, `symptom` | Discovery-first investigation of a single subsystem (cpu, memory, disk, network, process, or general). Includes namespace hints, hierarchical sampling, presentation standards, and guard clauses. |
| `incident_triage` | `symptom` | `host`, `timerange` | Maps a natural-language symptom to likely subsystems, confirms host-specific vs fleet-wide scope, performs rapid broad assessment, and delivers ranked findings with recommended actions. |
| `compare_periods` | `baseline_start`, `baseline_end`, `comparison_start`, `comparison_end` | `host`, `subsystem`, `context` | Broad-scan-first comparison between two time windows, ranked by magnitude of change, with overlap detection guard and root-cause hypothesis. |
| `fleet_health_check` | _(none)_ | `timerange`, `subsystems`, `detail_level` | Enumerates all fleet hosts, checks default subsystems (cpu, memory, disk, network), and produces a host-by-subsystem summary table with OK/WARN/CRIT indicators. Use `detail_level=detailed` to drill into anomalous hosts. |

All prompts follow a **discovery-first** pattern (enumerate available metrics before
assuming any metric names) and include guard clauses for missing tools, no-metrics-found,
and out-of-retention timeranges.

## Example Queries

```
What hosts are being monitored by PCP?

What CPU metrics are available on host web-01?

Show me the current CPU utilisation and memory usage on web-01.

Response times have been terrible for the last 2 hours. What's going on?

Compare this week's performance to last week for all hosts.

Give me a summary of all services over the past 7 days, highlighting anything that's degraded.
```

## Try It Out Locally

No PCP infrastructure? No problem — the bundled compose stack spins up a fully functional
PCP + Redis environment in under a minute.

### 1. Start the test harness

```bash
docker compose up -d
```

This starts:
- `quay.io/performancecopilot/pcp` — pmcd + pmproxy (port 44322)
- `redis/redis-stack` — time-series backend for historical queries (port 6379)

Wait ~10 seconds for pmproxy to initialise, then verify:

```bash
curl http://localhost:44322/series/query?expr=kernel.all.load
```

### 2. Build the pmmcp container

> **Note:** The image is not yet published to a registry ([#1](https://github.com/anthropics/pmmcp/issues/1)).
> Build it locally first.

```bash
docker build -t pmmcp .
```

### 3. Wire it up in Claude Code

Add this to `.mcp.json` in your project root (or `~/.claude/mcp.json` for global config):

```json
{
  "mcpServers": {
    "pmmcp": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "--name", "pmmcp", "pmmcp",
               "--pmproxy-url", "http://host.docker.internal:44322"]
    }
  }
}
```

`host.docker.internal` resolves to your host machine from inside the container — the
same host where the compose stack is listening on port 44322.

### 4. Tear down when done

```bash
docker compose down
```

## Development Setup

```bash
git clone <repository-url>
cd pmmcp
uv sync --extra dev

# Run tests
uv run pytest

# Run with coverage
uv run pytest --cov=pmmcp --cov-report=term-missing

# Lint
uv run ruff check src/ tests/

# Format
uv run ruff format src/ tests/
```

### Running against a real pmproxy

```bash
export PMPROXY_URL=http://your-pmproxy-host:44322
uv run pytest tests/integration/
```

Integration tests are skipped automatically when `PMPROXY_URL` is not set.

## Troubleshooting

**"Connection refused"**
- Verify pmproxy is running: `systemctl status pmproxy`
- Check the URL and port in your MCP configuration
- Ensure firewall allows access to port 44322: `curl http://your-pmproxy-host:44322/series/sources`

**"No time series data available"**
- Time-series queries require pmproxy's `[pmseries]` section to be configured with Valkey/Redis
- Verify: `curl http://your-pmproxy-host:44322/series/query?expr=kernel.all.load`

**"No metrics found"**
- Verify PCP collectors are running: `pminfo -f kernel.all.load`
- Check pmproxy connectivity: `curl http://your-pmproxy-host:44322/pmapi/metric?prefix=kernel`

**Slow responses**
- Reduce the time window or use a coarser interval
- Use fewer metrics per query
- Check pmproxy and Valkey/Redis performance independently
