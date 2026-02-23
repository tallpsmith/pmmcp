# Quickstart: pmmcp

**Feature**: 001-pcp-mcp-service
**Date**: 2026-02-21

## Prerequisites

- **PCP** installed and running on at least one monitored host
- **pmproxy** running and accessible (default port: 44322)
  - For time-series and multi-host features: pmproxy must be configured with a Valkey/Redis backend
- **Claude Code** installed
- **One of**: Python 3.11+ **or** Docker

## Installation

Choose **one** of the following methods:

### Option A: Docker (recommended for quick start)

No Python required. Pull the pre-built container:

```bash
docker pull ghcr.io/<org>/pmmcp
```

### Option B: Python Package

```bash
# From PyPI (once published)
pip install pmmcp

# Or from source
git clone <repository-url>
cd pmmcp
pip install -e .
```

## Configure Claude Code

Add pmmcp to your Claude Code MCP configuration. Create or edit `.mcp.json` in your project root.

### If using Docker:

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

### If using uvx (no install needed):

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

### If installed from source:

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

## Install Subagents (Optional)

Copy the companion subagent definitions to your Claude Code agents directory:

```bash
cp agents/*.md ~/.claude/agents/
```

This gives you four specialized agents:
- **performance-investigator** — diagnose performance problems
- **metric-explorer** — discover and explain available metrics
- **performance-comparator** — compare time periods
- **performance-reporter** — generate structured performance reports

## Verify It Works

Start Claude Code and try:

```
What hosts are being monitored by PCP?
```

You should see a list of hosts returned by pmproxy. If you get a connection error, verify that pmproxy is running and accessible from your machine:

```bash
curl http://your-pmproxy-host:44322/series/sources
```

## Example Usage

### Discover metrics
```
What CPU metrics are available on host web-01?
```

### Check live values
```
Show me the current CPU utilisation and memory usage on web-01
```

### Investigate a problem
```
Response times have been terrible for the last 2 hours. What's going on?
```

### Compare time periods
```
Compare this week's performance to last week for all hosts
```

### Generate a report
```
Give me a summary of all services over the past 7 days, highlighting anything that's degraded
```

## Development Setup

```bash
# Clone and install with dev dependencies
git clone <repository-url>
cd pmmcp
pip install -e ".[dev]"

# Run tests
pytest

# Run linter
ruff check src/ tests/

# Run formatter
ruff format src/ tests/

# Run with coverage
pytest --cov=pmmcp --cov-report=term-missing
```

## Troubleshooting

**"Connection refused" or connection errors**
- Verify pmproxy is running: `systemctl status pmproxy`
- Check the URL and port in your `.mcp.json` configuration
- Ensure firewall allows access to port 44322

**"No time series data available"**
- Time-series queries require pmproxy to be configured with a Valkey/Redis backend
- Check: `curl http://your-pmproxy-host:44322/series/query?expr=kernel.all.load`
- If this returns an empty array, configure pmproxy's `[pmseries]` section

**"No metrics found"**
- Verify PCP collectors are running on the target host: `pminfo -f kernel.all.load`
- Check that pmproxy can reach the host: `curl http://your-pmproxy-host:44322/pmapi/metric?prefix=kernel`

**Tool responses are slow**
- Reduce the time window or increase the sampling interval
- Use fewer metrics per query
- Check pmproxy and Valkey/Redis performance independently
