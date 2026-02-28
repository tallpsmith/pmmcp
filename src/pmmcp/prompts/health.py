"""MCP Prompt: fleet_health_check — Fleet-Wide Health Check Workflow.

Absorbs content from agents/performance-reporter.md.
"""

from __future__ import annotations

from pmmcp.server import mcp

_DEFAULT_SUBSYSTEMS = "cpu,memory,disk,network"

# KPI thresholds from performance-reporter.md
_KPI_TABLE = """\
| Subsystem | Key Metrics | Units | Concern Threshold |
|-----------|-------------|-------|------------------|
| CPU | `kernel.all.cpu.user` + `kernel.all.cpu.sys` (rate-converted) | % | > 80% sustained |
| Memory | `mem.util.used` / `mem.util.physmem` | % utilisation | > 90% |
| Disk I/O | `disk.all.avactive` | ms service time | > 100 ms |
| Network | `network.interface.out.bytes` (rate-converted) | Kbytes/s | Interface-dependent |
| Load | `kernel.all.load` (1-minute instance) | processes | > 2× ncpu |
"""


def _fleet_health_check_impl(
    timerange: str | None = None,
    subsystems: str | None = None,
    detail_level: str | None = None,
) -> list[dict]:
    """Pure function returning the fleet_health_check prompt messages.

    Testable without MCP infrastructure.
    """
    effective_subsystems = subsystems if subsystems else _DEFAULT_SUBSYSTEMS
    effective_detail = detail_level if detail_level else "summary"
    timerange_clause = (
        f"**Timerange**: {timerange}" if timerange else "**Timerange**: last 1 hour (default)"
    )

    drill_down_section = ""
    if effective_detail == "detailed":
        drill_down_section = """
## Step 5 — Detailed Drill-Down (detail_level=detailed)

For each host marked WARN or CRIT in the summary table:
1. Use `pcp_fetch_timeseries` at fine intervals (5 min, then 15s for peak windows) to \
identify the anomaly onset.
2. Correlate across subsystems: CPU saturation → disk I/O wait; memory pressure → swap \
activity; network saturation → connection timeouts.
3. Use `pcp_derive_metric` to rate-convert counters where needed.
4. Report a detailed findings section per anomalous host with:
   - Anomaly timeline
   - Supporting metric values
   - Root cause hypothesis
   - Recommended immediate actions

"""

    content = f"""\
You are performing a fleet-wide health check.

- **Subsystems**: {effective_subsystems}
- {timerange_clause}
- **Detail level**: {effective_detail}

## Guard Clauses — Check Before Proceeding

1. **Missing tool abort**: If any required tool (pcp_get_hosts, pcp_discover_metrics, \
pcp_fetch_timeseries, pcp_query_series) is missing or unavailable, stop immediately and \
report which tool is absent. Do not attempt the health check without it.

2. **No hosts found — stop**: After calling `pcp_get_hosts`, if no hosts are registered \
in the fleet, stop and report "no hosts found". Suggest the user verify their monitoring \
configuration and ensure at least one host is being monitored.

3. **No metrics found — stop**: After discovery, if no metrics are found for a target \
subsystem on any host, report "no metrics found for this subsystem" and stop. Do not \
silently skip subsystems.

4. **Out-of-retention — stop**: If the requested timerange falls outside the pmproxy \
retention window, stop and suggest a shorter, more recent timerange. Do not attempt to \
fetch data beyond the retention boundary.

## Step 1 — Host Enumeration

Call `pcp_get_hosts` to enumerate all monitored hosts in the fleet. \
This is mandatory before any other action — the health check scope is the full host list.

If no hosts are found, stop immediately with a message directing the user to verify \
their monitoring configuration.

## Step 2 — Discovery First

Use `pcp_discover_metrics` to enumerate available metrics in the target subsystems: \
**{effective_subsystems}**. Do not hardcode metric names — discover what is present.

Use `pcp_search` to find relevant metrics by keyword if needed. \
Use `pcp_get_metric_info` to check semantics (counter vs instant) before fetching.

## Step 3 — Fleet-Wide KPI Collection

For each host, collect the following default KPIs at the configured timerange and \
`1hour` interval (adjust to `5min` for timeranges < 6 hours):

{_KPI_TABLE}

Use `pcp_fetch_timeseries` for each host and subsystem combination. \
Rate-convert counters (CPU ms → %, disk bytes/s → MB/s, network bytes/s → Mbps).

**Presentation standards**:
- CPU: express as **percentage** (`rate_ms_per_sec / (hinv.ncpu × 10)`)
- Memory: `mem.util.*` in Kbytes → normalise to MB or **GB** (e.g. `6.2 GB / 8 GB`)
- Disk throughput: Kbytes/s after rate conversion → **MB/s**; service time stays as **ms**
- Network: normalise to KB/s, **MB/s**, or Gbps — whichever avoids numbers > 1000
- Load: report relative to CPU count (e.g. `2.4 / 8 CPUs = 30% saturated`)

## Step 4 — Summary Table

Produce a concise host-by-subsystem summary table with status indicators:

| Host | CPU% (mean/p95) | Mem% | Disk I/O (ms) | Net (MB/s) | Load | Status |
|------|----------------|------|---------------|-----------|------|--------|
| host1 | 23% / 45% | 67% | 12ms | 45 | 1.2 / 8 | ✓ OK |
| host2 | 78% / 95% | 88% | 145ms | 820 | 3.1 / 4 | ⚠ WARN |

Status indicator rules:
- **✓ OK**: All KPIs within normal thresholds
- **⚠ WARN**: Any KPI approaching or above concern threshold (but < 2× threshold)
- **✗ CRIT**: Any KPI at 2× threshold or above, or any KPI in a critical state
{drill_down_section}
## Step {6 if effective_detail == "detailed" else 5} — Trend Classification

For each significant metric, classify the trend by comparing the first half vs second \
half of the assessment period using `pcp_compare_windows`:
- **Improving**: mean_change < 0 and significant (utilisation decreasing)
- **Degrading**: mean_change > 0 and significant (utilisation increasing)
- **Stable**: significant == false

## Final Report Structure

1. **Fleet health summary** (1–2 sentences): overall health, largest concerns
2. **Per-host KPI table** (Step 4 format above)
3. **Notable anomalies**: specific hosts and time windows where metrics deviated
4. **Recommendations**: actionable items, e.g. investigate CRIT hosts, plan capacity
"""

    return [{"role": "user", "content": content}]


@mcp.prompt()
def fleet_health_check(
    timerange: str | None = None,
    subsystems: str | None = None,
    detail_level: str | None = None,
) -> list[dict]:
    """Fleet-wide health check with per-host summary table and status indicators.

    Enumerates all monitored hosts, checks each configured subsystem, and
    produces a concise host-by-subsystem summary table with status indicators
    (OK/WARN/CRIT). Includes guard clauses for missing tools, no-hosts-found
    (stop + config suggestion), no-metrics-found, and out-of-retention
    timeranges. Optionally drills into anomalous hosts at detail_level=detailed.

    Args:
        timerange: Assessment window in pmproxy format e.g. -1hours (optional, default: -1hours)
        subsystems: Comma-separated subsystems to check (optional, default: cpu,memory,disk,network)
        detail_level: Output depth — 'summary' (default) or 'detailed' (drill into anomalous hosts)
    """
    return _fleet_health_check_impl(timerange, subsystems, detail_level)
