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
- **One of**: Python 3.11+ with [uv](https://docs.astral.sh/uv/) or Docker

## Installation

> **Note:** Docker image and PyPI package publishing are not yet available. Install from source for now.

### From Source

```bash
git clone <repository-url>
cd pmmcp
uv sync          # installs pmmcp and its dependencies into the uv-managed venv
```

## Configure Claude Code

Add pmmcp to `.mcp.json` in your project root (or `~/.claude/mcp.json` for global config).

### Python (installed from source)

> **Prerequisite:** Run `uv sync` from the repo root first (see Installation above).

```json
{
  "mcpServers": {
    "pmmcp": {
      "command": "uv",
      "args": ["run", "pmmcp", "--pmproxy-url", "http://your-pmproxy-host:44322"]
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

No PCP infrastructure? No problem. The bundled compose stack generates a week of
realistic synthetic performance data — a SaaS production host with daily traffic
patterns, morning ramps, lunch lulls, and periodic CPU/disk spikes — seeds it into
pmproxy's time-series backend, and has everything ready for Claude to analyse.

### 1. Start the stack

```bash
podman compose up -d
```

This runs four services in order:

1. **pmlogsynth-generator** — generates PCP archives from `profiles/scenarios/saas-diurnal-week.yml`
2. **redis-stack** — time-series backend (Valkey/Redis, port 6379)
3. **pmlogsynth-seeder** — loads the archives into the time-series store
4. **pcp** — pmcd + pmproxy, ready to serve queries (port 44322)

The generator and seeder are one-shot jobs; allow ~30–60 seconds for them to complete
before pmproxy is ready. Check progress with:

```bash
podman compose logs -f pmlogsynth-generator pmlogsynth-seeder
```

Once seeded, verify data is queryable:

```bash
curl -s "http://localhost:44322/series/query?expr=kernel.all.cpu.user" | head -c 200
```

### 2. Connect pmmcp to Claude Code

Install pmmcp from source (one-time):

```bash
uv sync
```

Add this to `.mcp.json` in your project root (or `~/.claude/mcp.json` for global config):

```json
{
  "mcpServers": {
    "pmmcp": {
      "command": "uv",
      "args": ["run", "pmmcp", "--pmproxy-url", "http://localhost:44322"]
    }
  }
}
```

Restart Claude Code (or run `/mcp` to reload) and confirm **pmmcp** appears in the
connected servers list.

### 3. Ask Claude to investigate

The seeded dataset is `saas-prod-01` — a simulated production host with a week of
realistic diurnal traffic. Try these to get a feel for what pmmcp can do:

**Explore the data:**
```
What hosts and metrics are available?
```

**Spot the daily pattern:**
```
Show me CPU utilisation on saas-prod-01 over the past 7 days.
Are there any recurring spikes?
```

**Drill into an incident:**
```
There's a CPU and disk spike that seems to happen every day on saas-prod-01.
When exactly does it occur, how severe is it, and how long does it last?
```

**Compare periods:**
```
Compare the morning peak period to the overnight baseline on saas-prod-01.
What's the magnitude of the difference across CPU, memory, disk, and network?
```

**Use a prompt template for guided investigation:**
```
/investigate_subsystem subsystem=cpu host=saas-prod-01
```

### 4. Tear down when done

```bash
podman compose down --volumes
```

`--volumes` purges the generated archive data so the next `up` starts fresh.

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
