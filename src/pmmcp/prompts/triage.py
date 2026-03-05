"""MCP Prompt: incident_triage — Live Incident Triage Workflow.

Wholly new capability — no agent to retire.
"""

from __future__ import annotations

from pmmcp.server import mcp

# Symptom-to-subsystem mapping (natural language heuristics)
_SYMPTOM_MAP = """\
## Symptom-to-Subsystem Mapping

Use these heuristics to identify the most likely subsystems based on the symptom description:

| Symptom keywords                                  | Primary subsystems to investigate         |
|---------------------------------------------------|-------------------------------------------|
| "slow", "latency", "response time", "timeout"    | cpu, disk, network                        |
| "memory", "OOM", "swap", "out of memory"         | memory                                    |
| "CPU", "load", "utilisation", "load average"     | cpu, process                              |
| "disk", "I/O", "iops", "throughput", "storage"  | disk                                      |
| "network", "bandwidth", "packet loss", "drops"  | network                                   |
| "process", "crashed", "OOM kill", "zombie"       | process, memory                           |
| "down", "unavailable", "unreachable"             | network, cpu, disk                        |
| "degraded", "slow", "intermittent"               | cpu, disk, network, memory                |

If the symptom cannot be mapped to any of the above, or the keywords are ambiguous, fall back to a \
**broad general investigation across all subsystems** (cpu, memory, disk, network, process). \
Note in your report that the symptom was ambiguous and a full sweep was performed.
"""


def _incident_triage_impl(
    symptom: str,
    host: str | None = None,
    timerange: str | None = None,
) -> list[dict]:
    """Pure function returning the incident_triage prompt messages.

    Testable without MCP infrastructure.
    """
    host_clause = f" on host **{host}**" if host else " (all hosts)"
    timerange_clause = (
        f" for the window **{timerange}**" if timerange else " (default: last 1 hour)"
    )

    content = f"""\
You are triaging a live incident. The reported symptom is:

> **{symptom}**

Scope: {host_clause}{timerange_clause}

## Guard Clauses — Check Before Proceeding

1. **Missing tool abort**: If any required tool is missing or unavailable, stop \
immediately and report which tool is absent. Do not attempt the triage without it.

2. **Out-of-retention — stop**: If the requested timerange falls outside the pmproxy \
retention window, stop and suggest a shorter, more recent timerange. Do not attempt to \
fetch data beyond the retention boundary.

## Preparation — Interpret Symptom and Confirm Scope

{_SYMPTOM_MAP}

Based on the symptom above, identify the 1–3 most likely subsystems and start there. \
If the symptom is unmappable or ambiguous, proceed with a general sweep across all \
subsystems (cpu, memory, disk, network, process) and note in your report that a full \
sweep was performed due to ambiguous symptom.

Use `pcp_get_hosts` to enumerate all monitored hosts. If `host` was specified, confirm \
it is registered. Check whether the issue is **host-specific** or **fleet-wide** by \
examining the specified host first, then 2–3 others. Report clearly before proceeding.

Use `pcp_discover_metrics` to enumerate available metrics in the target subsystems. \
Do not assume metric names — discover what is actually present. Use `pcp_search` to find \
additional relevant metrics by keyword. Use `pcp_get_metric_info` to check semantics \
(counter vs instant) before fetching.

**No-metrics-found — stop**: If no metrics are found for a targeted subsystem, report \
"no metrics found for this subsystem" and stop.

## Investigation Sequence

Execute these four steps in order. Each step informs the next.

## Step 1 — Anomaly Detection

Run `pcp_detect_anomalies` on the target metrics across the recent window versus a \
historical baseline. Use a baseline window at least 4× the length of the recent window \
(e.g., recent = last 1 hour, baseline = last 7 days). Cover all subsystems identified \
in the preparation phase.

If anomalies are found, proceed to Step 2. If no anomalies are detected, report \
"no baseline deviation found" and stop — do not continue to drilldown.

## Step 2 — Compare Windows

If anomalies are found in Step 1, call `pcp_compare_windows` to compare a known-good \
baseline window against the anomalous window. This quantifies the magnitude of change \
and identifies which metrics degraded most.

If significant differences are found, proceed to Step 3 to scan for broader changes. \
If differences are minimal, report findings and stop.

## Step 3 — Scan for Broader Changes

Call `pcp_scan_changes` across the affected metric namespace prefix \
(e.g., `kernel`, `mem`, `disk`, `network`) to discover any other metrics that changed \
between the good and bad windows. This surfaces correlated changes not captured in \
the initial anomaly detection.

Correlate across subsystems: CPU saturation drives disk I/O wait; memory pressure causes \
swap activity which manifests as disk I/O; network saturation causes application timeouts; \
runaway processes drive CPU and memory together.

Proceed to Step 4 only for the specific metrics confirmed as anomalous.

## Step 4 — Targeted Drilldown

Call `pcp_fetch_timeseries` **only** on the metrics confirmed as anomalous in Steps 1–3. \
Do not run timeseries fetch on all metrics. Start with a coarse interval to identify \
when the problem began, then drill down to finer granularity on the affected window.

## Findings

Report as:
1. **Incident scope** — host-specific or fleet-wide, affected hosts
2. **Root cause hypothesis** — the primary anomaly with supporting metric evidence
3. **Contributing factors** — secondary anomalies correlated with the primary
4. **Timeline** — when the anomaly began and its trajectory
5. **Recommended immediate actions** — what to do right now to reduce impact
6. **Escalation path** — if root cause cannot be identified from metrics alone
"""

    return [{"role": "user", "content": content}]


@mcp.prompt()
def incident_triage(
    symptom: str,
    host: str | None = None,
    timerange: str | None = None,
) -> list[dict]:
    """Live incident triage workflow with symptom-to-subsystem mapping.

    Interprets a natural-language symptom description to identify the most
    likely subsystems, confirms host-specific vs fleet-wide scope, performs
    a rapid broad assessment, and delivers a concise findings report with
    recommended actions. Includes guard clauses for missing tools,
    out-of-retention timeranges, and unmappable symptoms (general sweep
    fallback).

    Args:
        symptom: Natural-language description of the incident symptom (required)
        host: Target host to investigate first (optional — fleet-wide if omitted)
        timerange: Time window in pmproxy format e.g. -1hours, -7days (optional)
    """
    return _incident_triage_impl(symptom, host, timerange)
