"""MCP Prompt: investigate_subsystem — Guided Subsystem Investigation.

Absorbs content from agents/performance-investigator.md and agents/metric-explorer.md.
"""

from __future__ import annotations

from pmmcp.server import mcp

# Namespace hints per subsystem (natural language, not hardcoded metric names)
_SUBSYSTEM_HINTS: dict[str, str] = {
    "cpu": (
        "Focus on the `kernel.*` namespace: CPU time fractions (user/sys/idle/wait), "
        "per-CPU breakdown for SMP imbalance, runnable process count, and load average. "
        "Use `hinv.ncpu` to normalise CPU counters to percentage."
    ),
    "memory": (
        "Focus on the `mem.*` namespace: utilisation (used/free/available/swap), "
        "virtual memory statistics (page-in/out rates, swap rates). "
        "Any swap activity is a critical signal."
    ),
    "disk": (
        "Focus on the `disk.*` namespace: per-device IOPS and throughput "
        "(read/write bytes), I/O service time (avactive), and aggregated totals. "
        "High I/O service time combined with high CPU iowait indicates saturation."
    ),
    "network": (
        "Focus on the `network.*` namespace: bandwidth per interface (in/out bytes), "
        "error counters, and packet drops. Any drops indicate saturation or errors."
    ),
    "process": (
        "Focus on the `proc.*` namespace: total process count, run-queue depth, "
        "and per-process resource usage via hotproc if available."
    ),
    "general": (
        "Perform a broad sweep across all major namespaces: `kernel.*` (CPU/load), "
        "`mem.*` (memory/swap), `disk.*` (I/O), `network.*` (bandwidth/errors), "
        "and `proc.*` (process activity). Identify the dominant subsystem first, "
        "then drill down."
    ),
}


def _investigate_subsystem_impl(
    subsystem: str,
    host: str | None = None,
    timerange: str | None = None,
    symptom: str | None = None,
) -> list[dict]:
    """Pure function returning the investigate_subsystem prompt messages.

    Testable without MCP infrastructure.
    """
    host_clause = f" on host **{host}**" if host else " across all monitored hosts"
    timerange_clause = (
        f" for the window **{timerange}**" if timerange else " (default: last 1 hour)"
    )
    symptom_clause = f"\n\n**Reported symptom**: {symptom}" if symptom else ""

    namespace_hints = _SUBSYSTEM_HINTS.get(subsystem, _SUBSYSTEM_HINTS["general"])

    content = f"""\
You are conducting a **{subsystem}** performance investigation\
{host_clause}{timerange_clause}.{symptom_clause}

## Guard Clauses — Check Before Proceeding

1. **Missing tool abort**: If any required tool (pcp_get_hosts, pcp_discover_metrics, \
pcp_fetch_timeseries, pcp_query_sqlite) is missing or unavailable, stop immediately and \
report which tool is absent. Do not attempt the investigation without it.

2. **No metrics found — stop**: After discovery, if no metrics are found in the target \
namespace for the specified host and timerange, stop and report "no metrics found for \
{subsystem}". Do not proceed to fetch empty data.

3. **Out-of-retention — stop**: If the requested timerange falls outside the pmproxy \
retention window, stop and suggest a shorter, more recent timerange. Do not attempt to \
fetch data beyond the retention boundary.

## Step 1 — Infrastructure Check

Call `pcp_get_hosts` first. Confirm the target host exists{host_clause}. \
If the host is not found, report it and stop.

## Step 2 — Discovery First

Use `pcp_discover_metrics` to enumerate the available metric namespace before fetching \
any data. Do not hardcode metric names — discover what is actually present.

{namespace_hints}

Use `pcp_search` to find additional relevant metrics by keyword if needed. \
Use `pcp_get_metric_info` to check semantics (counter vs instant) before fetching.

## Step 3 — Hierarchical Sampling

Start **coarse** to identify *when* the problem began:
- Begin with a wide window (e.g., last 7 days at `1hour` interval) to spot the anomaly onset.
- Once the problem window is identified, **drill down** at finer intervals (e.g., last 2 hours \
at `5min`, then the peak 30 minutes at `15s`).
- Never start with a 15-second interval over a week — that produces thousands of points \
without context.

## Step 4 — Presentation Standards

Always report values in human-readable units:

- **CPU utilisation**: Express as **percentage (0–100%)**. `kernel.all.cpu.*` metrics are \
counters in ms. After rate conversion: `% = rate_ms_per_sec / (hinv.ncpu × 10)`. \
Show as `42%`, not raw milliseconds.
- **Memory**: `mem.util.*` metrics are in Kbytes. Normalise: < 1 GB → show as MB; \
≥ 1 GB → show as **GB** (e.g., `6.2 GB`). Never present raw Kbyte numbers.
- **Disk throughput**: `disk.dev.read_bytes` / `disk.dev.write_bytes` are Kbytes counters. \
After rate conversion, show as **MB/s**. I/O service time (`disk.dev.avactive`) is in ms.
- **Network bandwidth**: After rate conversion, show as KB/s, **MB/s**, or Gbps — whichever \
avoids numbers > 1000.
- **Load average**: Report relative to CPU count: e.g., `load 2.4 (30% saturated on 8-core host)`.
- **General rule**: If a value would print as `1,048,576` or `0.000042`, convert it. \
Prefer 1–3 significant figures.

## Step 5 — Counter vs Instant Semantics

- **Counters** (semantics=counter): Accumulate over time. Rate-convert via `pcp_derive_metric`: \
`derived.disk.iops = rate(disk.dev.read)`.
- **Instant/Gauge** (semantics=instant): Use directly — no conversion needed.
- Always check `pcp_get_metric_info` if unsure about semantics for an unfamiliar metric.

## Step 6 — Tool-Ordering Workflow

Follow this investigation sequence for best results:

1. **Start broad** with `pcp_quick_investigate` — pass the time of interest and optionally a \
subsystem prefix. This discovers all available metrics and returns the top anomalies ranked \
by z-score. Use this as your first move for open-ended investigation.
2. **Confirm findings** with `pcp_detect_anomalies` or `pcp_compare_windows` — take the \
anomalous metrics identified in step 1 and run targeted analysis with precise time windows \
to verify and quantify the anomaly.
3. **Retrieve detailed data** with `pcp_fetch_timeseries` — only for metrics confirmed as \
anomalous in step 2. Drill down to fine-grained time-series data for root cause analysis.

Do NOT jump straight to `pcp_fetch_timeseries` for exploration — it requires you to already \
know which metrics to look at.

## Step 7 — Findings Structure

Report findings as:
1. **Anomalies** (ranked by severity) — metric name, affected period, observed value vs baseline
2. **Supporting data** — key time-series data points showing the anomaly
3. **Likely root cause** — correlation of multiple metrics
4. **Recommended next steps** — immediate actions, further investigation, or escalation path
"""

    return [{"role": "user", "content": content}]


@mcp.prompt()
def investigate_subsystem(
    subsystem: str,
    host: str | None = None,
    timerange: str | None = None,
    symptom: str | None = None,
) -> list[dict]:
    """Guided subsystem performance investigation workflow.

    Provides a discovery-first investigation workflow for the specified subsystem
    (cpu, memory, disk, network, process, or general). Includes namespace hints,
    hierarchical sampling strategy, presentation standards, and guard clauses for
    missing tools, no-metrics-found, and out-of-retention scenarios.

    Args:
        subsystem: One of: cpu, memory, disk, network, process, general
        host: Target host to investigate (optional — all hosts if omitted)
        timerange: Time window in pmproxy format e.g. -1hours, -7days (optional)
        symptom: Natural-language description of the reported problem (optional)
    """
    return _investigate_subsystem_impl(subsystem, host, timerange, symptom)
