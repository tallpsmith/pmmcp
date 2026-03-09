# pmmcp — PCP MCP Service

<p align="center">
  <img src="logo.jpg" width="700">
</p>

An [MCP](https://modelcontextprotocol.io) server that exposes [Performance Co-Pilot (PCP)](https://pcp.io) metrics to AI agents via [pmproxy](https://man7.org/linux/man-pages/man1/pmproxy.1.html). Enables Claude and other LLMs to query live and historical performance data from any PCP-monitored host.

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

The generator and seeder are one-shot jobs; allow ~30–60 seconds for them to complete.
Check progress with:

```bash
podman compose logs -f pmlogsynth-generator pmlogsynth-seeder
```

Once seeded, verify data is queryable:

```bash
curl -s "http://localhost:44322/series/query?expr=kernel.all.cpu.user" | head -c 200
```

### 2. Connect pmmcp to Claude Code

```bash
git clone <repository-url>
cd pmmcp
uv sync
```

Add to `.mcp.json` in your project root (or `~/.claude/mcp.json` for global config):

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

Restart Claude Code (or `/mcp` to reload) and confirm **pmmcp** appears in the connected servers list.

### 3. Ask Claude to investigate

The seeded dataset is `saas-prod-01` — a simulated production host with a week of
realistic diurnal traffic. Try these to get a feel for what pmmcp can do:

**Explore the data:**
```
What hosts and metrics are available?
```

**Spot the daily pattern:**
```
Show me CPU utilisation on saas-prod-01 over the past 7 days. Are there any recurring spikes?
```

**Drill into an incident:**
```
There's a CPU and disk spike that seems to happen every day on saas-prod-01.
When exactly does it occur, how severe is it, and how long does it last?
```

**Compare periods:**
```
Compare the morning peak to the overnight baseline on saas-prod-01 across CPU, memory, disk, and network.
```

**Use a prompt template for a guided investigation workflow:**
```
/investigate_subsystem subsystem=cpu host=saas-prod-01
```

### 4. Tear down when done

```bash
podman compose down --volumes
```

`--volumes` purges the generated archive data so the next `up` starts fresh.

## What It Does

pmmcp gives AI agents 9 MCP tools and 7 MCP prompt templates for performance investigation. See [Investigation Flow Architecture](docs/investigation-flow.md) for how the coordinator-specialist pattern works.

**Tools**

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

**Prompt templates**

Invoke any prompt from your MCP client to get a guided investigation workflow. All
prompts follow a **discovery-first** pattern and include guard clauses for missing
tools, no-metrics-found, and out-of-retention timeranges.

| Prompt | Required args | Optional args | What it does |
|--------|--------------|---------------|--------------|
| `session_init` | _(none)_ | `host`, `timerange` | Registers derived metrics, then points to `coordinate_investigation` |
| `coordinate_investigation` | `request` | `host`, `time_of_interest`, `lookback` | Dispatches 6 specialists in parallel, synthesises unified root-cause narrative |
| `specialist_investigate` | `subsystem` | `request`, `host`, `time_of_interest`, `lookback` | Deep domain-expert investigation for one subsystem |
| `investigate_subsystem` | `subsystem` | `host`, `timerange`, `symptom` | Discovery-first investigation of a single subsystem (cpu, memory, disk, network, process, or general) |
| `incident_triage` | `symptom` | `host`, `timerange` | Maps a symptom to likely subsystems, confirms host-specific vs fleet-wide scope, delivers ranked findings with recommended actions |
| `compare_periods` | `baseline_start`, `baseline_end`, `comparison_start`, `comparison_end` | `host`, `subsystem`, `context` | Broad-scan comparison between two time windows, ranked by magnitude of change, with root-cause hypothesis |
| `fleet_health_check` | _(none)_ | `timerange`, `subsystems`, `detail_level` | Checks all fleet hosts across default subsystems and produces a host-by-subsystem summary with OK/WARN/CRIT indicators |

## Connect to Your Infrastructure

### Prerequisites

- PCP installed and running on at least one monitored host
- pmproxy running and accessible (default port: 44322)
  - Time-series tools (`pcp_fetch_timeseries`, `pcp_query_series`, `pcp_compare_windows`) require pmproxy configured with a Valkey/Redis backend
- Python 3.11+ with [uv](https://docs.astral.sh/uv/)
- Claude Code or another MCP client

### Install and configure

```bash
git clone <repository-url>
cd pmmcp
uv sync
```

Add to `.mcp.json`:

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

Add `"--timeout", "60"` to `args` if you need a longer HTTP timeout (default: 30s).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

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
