# pmmcp — PCP MCP Service

An [MCP](https://modelcontextprotocol.io) server that exposes [Performance Co-Pilot (PCP)](https://pcp.io) metrics to AI agents via [pmproxy](https://man7.org/linux/man-pages/man1/pmproxy.1.html). Enables Claude and other LLMs to query live and historical performance data from any PCP-monitored host.

## What It Does

pmmcp gives AI agents 9 MCP tools for performance investigation:

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

### Option A: Docker (recommended)

```bash
docker pull ghcr.io/<org>/pmmcp
```

### Option B: From PyPI

```bash
pip install pmmcp
```

### Option C: From Source

```bash
git clone <repository-url>
cd pmmcp
pip install -e .
```

## Configure Claude Code

Add pmmcp to `.mcp.json` in your project root (or `~/.claude/mcp.json` for global config).

### Docker

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

### uvx (no install needed)

```json
{
  "mcpServers": {
    "pmmcp": {
      "command": "uvx",
      "args": ["pmmcp", "--pmproxy-url", "http://your-pmproxy-host:44322"]
    }
  }
}
```

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

## Install Subagents (Optional)

Copy the companion subagent definitions to your Claude Code agents directory:

```bash
cp agents/*.md ~/.claude/agents/
```

This gives you four specialized agents:

- **performance-investigator** — diagnose performance problems interactively
- **metric-explorer** — discover and explain available metrics
- **performance-comparator** — compare two time periods statistically
- **performance-reporter** — generate structured performance reports

## Example Queries

```
What hosts are being monitored by PCP?

What CPU metrics are available on host web-01?

Show me the current CPU utilisation and memory usage on web-01.

Response times have been terrible for the last 2 hours. What's going on?

Compare this week's performance to last week for all hosts.

Give me a summary of all services over the past 7 days, highlighting anything that's degraded.
```

## Development Setup

```bash
git clone <repository-url>
cd pmmcp
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=pmmcp --cov-report=term-missing

# Lint
ruff check src/ tests/

# Format
ruff format src/ tests/
```

### Running against a real pmproxy

```bash
export PMPROXY_URL=http://your-pmproxy-host:44322
pytest tests/integration/
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
