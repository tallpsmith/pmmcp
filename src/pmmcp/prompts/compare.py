"""MCP Prompt: compare_periods — Before/After Period Comparison Workflow.

Absorbs content from agents/performance-comparator.md.
"""

from __future__ import annotations

from pmmcp.server import mcp


def _compare_periods_impl(
    baseline_start: str,
    baseline_end: str,
    comparison_start: str,
    comparison_end: str,
    host: str | None = None,
    subsystem: str | None = None,
    context: str | None = None,
) -> list[dict]:
    """Pure function returning the compare_periods prompt messages.

    Testable without MCP infrastructure.
    """
    host_clause = f" on host **{host}**" if host else " (all hosts)"
    subsystem_clause = f" scoped to the **{subsystem}** subsystem" if subsystem else ""
    context_clause = f"\n\n**Change context**: {context}" if context else ""
    discovery_scope = (
        f"Since the comparison is scoped to **{subsystem}**, "
        f"focus discovery on that subsystem's namespace."
        if subsystem
        else (
            "Start broad across all major namespaces: `kernel.*` (CPU), `mem.*` (memory), "
            "`disk.*` (I/O), `network.*` (bandwidth/errors), `proc.*` (processes)."
        )
    )

    content = f"""\
You are performing a before/after performance comparison.{context_clause}

- **Baseline window**: {baseline_start} → {baseline_end}
- **Comparison window**: {comparison_start} → {comparison_end}
- **Scope**: {host_clause}{subsystem_clause}

## Guard Clauses — Check Before Proceeding

1. **Missing tool abort**: If any required tool (pcp_get_hosts, pcp_discover_metrics, \
pcp_fetch_timeseries, pcp_compare_windows, pcp_query_series) is missing or unavailable, \
stop immediately and report which tool is absent. Do not attempt the comparison without it.

2. **Overlap detection — stop**: Before fetching any data, verify that the baseline and \
comparison windows do **not** overlap. Overlapping windows produce unreliable results \
because the same data points appear in both windows, making the comparison meaningless. \
If overlap is detected, report it as invalid input, explain why overlapping windows are \
unreliable, and stop — ask the user to provide non-overlapping windows.

3. **Out-of-retention — stop**: If either window falls outside the pmproxy retention \
window, stop and suggest adjusting the timerange to a more recent, retained period. \
Do not attempt to fetch data beyond the retention boundary.

## Step 1 — Infrastructure and Scope Check

1. Call `pcp_get_hosts` to confirm which hosts are available.
2. If `host` was specified, verify it exists. If not found, report and stop.
3. If no host was specified, the comparison will span all monitored hosts — identify \
which hosts show the largest delta in the findings.

## Step 2 — Broad Scan First (Discovery-First)

Use `pcp_discover_metrics` to enumerate the available metric namespace. \
Do not assume metric names — discover what is actually present.

{discovery_scope}

Use `pcp_search` to find additional relevant metrics by keyword. \
Use `pcp_get_metric_info` to check semantics (counter vs instant) before comparing.

**No-metrics-found — stop**: If no metrics are found for the target namespace, report \
"no metrics found" and stop. Do not proceed with empty data.

## Step 3 — Hierarchical Comparison

Perform the scan in passes to keep it efficient:

1. **First pass — broad aggregates**: Compare 4–6 key aggregate metrics across all \
major subsystems using `pcp_compare_windows`. Identify which subsystems changed.
2. **Second pass — subsystem drill-down**: For each subsystem that shows significant \
change, compare specific sub-metrics (e.g., per-CPU, per-disk, per-interface).
3. **Third pass** (if needed): Per-instance breakdowns for the most affected devices.

Do not start with per-instance metrics — that produces noise without context.

## Step 4 — Statistical Interpretation

When interpreting `pcp_compare_windows` results:

| Field | What it means |
|-------|---------------|
| `mean_change` | Average level shifted by this amount |
| `mean_change_pct` | Percentage change in average level |
| `stddev_change` | Variability changed (positive = more jitter) |
| `significant` | True when mean shift > 2× baseline stddev |

Focus on `significant == true` findings first.

**Context matters**: A 50% CPU increase at 2% baseline is noise; the same increase \
at 80% baseline indicates saturation. Always report both the absolute level and the \
percentage change together.

## Step 5 — Rank by Magnitude of Change

Sort all findings by magnitude of change (largest `mean_change_pct` first). \
Present results as a ranked table:

| Metric | Baseline | Comparison | Change | Significant? | Interpretation |
|--------|----------|------------|--------|--------------|----------------|

Rules for the table:
- Use the same unit in both columns (e.g., both as `%`, both as `MB/s`)
- CPU: express as **percentage** (rate_ms_per_sec ÷ (hinv.ncpu × 10))
- Memory: `mem.util.*` in Kbytes → normalise to MB or **GB**
- Disk: `disk.dev.*_bytes` in Kbytes/s after rate conversion → show as **MB/s**
- Network: normalise to KB/s, **MB/s**, or Gbps — whichever avoids numbers > 1000
- Never show raw counter values; rate-convert counters first

## Step 6 — Common Patterns to Identify

- **Sudden step change**: Baseline mean is stable; comparison mean jumps — suggests \
a change event (deployment, configuration change, traffic spike)
- **Gradual drift**: Comparison mean higher, stddev similar — suggests resource leak \
or steady load increase
- **Increased variability**: Comparison stddev >> baseline stddev — suggests \
intermittent load spikes or contention

## Step 7 — Root Cause Hypothesis and Recommendations

Report:
1. **Summary**: Which subsystems changed significantly, ranked by magnitude
2. **Root cause hypothesis**: The primary correlation pattern observed (e.g., \
"CPU saturation drove disk I/O wait increase and network latency spikes")
3. **Affected hosts**: Which hosts showed the largest delta (if fleet-wide)
4. **Recommended drill-down**: Specific metrics or subsystems warranting \
further investigation
5. **Next steps**: Immediate actions, configuration changes, or escalation path
"""

    return [{"role": "user", "content": content}]


@mcp.prompt()
def compare_periods(
    baseline_start: str,
    baseline_end: str,
    comparison_start: str,
    comparison_end: str,
    host: str | None = None,
    subsystem: str | None = None,
    context: str | None = None,
) -> list[dict]:
    """Before/after performance comparison with magnitude-ranked findings.

    Performs a broad-scan-first comparison between two time windows,
    ranks changed metrics by magnitude, identifies affected hosts, and
    produces a root-cause hypothesis. Includes guard clauses for missing
    tools, overlapping windows (invalid input, stop), and out-of-retention
    timeranges.

    Args:
        baseline_start: Start of baseline window in pmproxy time format (required)
        baseline_end: End of baseline window in pmproxy time format (required)
        comparison_start: Start of comparison window in pmproxy time format (required)
        comparison_end: End of comparison window in pmproxy time format (required)
        host: Restrict comparison to a specific host (optional — all hosts if omitted)
        subsystem: Restrict to a specific subsystem e.g. cpu, disk (optional)
        context: Description of what changed between the windows (optional)
    """
    return _compare_periods_impl(
        baseline_start,
        baseline_end,
        comparison_start,
        comparison_end,
        host,
        subsystem,
        context,
    )
