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

1. **Missing tool abort**: If any required tool (pcp_get_hosts, pcp_discover_metrics, \
pcp_fetch_timeseries, pcp_query_series, pcp_fetch_live) is missing or unavailable, stop \
immediately and report which tool is absent. Do not attempt the triage without it.

2. **Out-of-retention — stop**: If the requested timerange falls outside the pmproxy \
retention window, stop and suggest a shorter, more recent timerange. Do not attempt to \
fetch data beyond the retention boundary.

## Step 1 — Interpret Symptom and Identify Likely Subsystems

{_SYMPTOM_MAP}

Based on the symptom above, identify the 1–3 most likely subsystems and start there. \
If the symptom is unmappable or ambiguous, proceed with a general sweep across all \
subsystems (cpu, memory, disk, network, process) and note in your report that a full \
sweep was performed due to ambiguous symptom.

## Step 2 — Scope Confirmation: Host-Specific vs Fleet-Wide

1. Call `pcp_get_hosts` to enumerate all monitored hosts.
2. If `host` was specified, confirm it is registered. If not found, report and stop.
3. Check whether the anomaly is **host-specific** or **fleet-wide**:
   - Start with the specified host (if provided) — investigate it first.
   - Then check 2–3 other hosts in the fleet to determine if the issue is isolated.
   - Report clearly: "Issue appears host-specific to <host>" or "Issue is fleet-wide \
(observed on N hosts)".
4. If no host was specified, begin fleet-wide and identify which hosts show the anomaly.

Do not drill into root cause until you have determined the scope.

## Step 3 — Discovery First

Use `pcp_discover_metrics` to enumerate available metrics in the target subsystems. \
Do not assume metric names — discover what is actually present.

Use `pcp_search` to find additional relevant metrics by keyword. \
Use `pcp_get_metric_info` to check semantics (counter vs instant) before fetching.

**No-metrics-found — stop**: If no metrics are found for a targeted subsystem, report \
"no metrics found for this subsystem" and stop. Do not silently fall back or proceed \
with empty data.

## Step 4 — Rapid Broad Assessment

Start with a coarse window to identify *when* the problem began:
- Fetch the last hour at `5min` intervals to spot the anomaly onset and affected hosts.
- Once the problem window is identified, **drill down** at finer intervals (e.g., peak \
15 minutes at `15s`) on the affected host(s) and subsystems.
- Do not start with 15-second intervals over a long window — that produces noise.

## Step 5 — Root Cause Correlation

Correlate across subsystems:
- CPU saturation often drives disk I/O wait and network latency.
- Memory pressure causes swap activity which manifests as disk I/O.
- Network bandwidth saturation can cause application timeout symptoms.
- High process count or runaway processes drive CPU and memory consumption.

Report correlated findings together rather than as isolated observations.

## Step 6 — Findings and Recommended Actions

Report as:
1. **Incident scope** — host-specific or fleet-wide, affected hosts
2. **Root cause hypothesis** — the primary anomaly with supporting metric evidence
3. **Contributing factors** — secondary anomalies correlated with the primary
4. **Timeline** — when the anomaly began and its trajectory
5. **Recommended immediate actions** — what to do right now to reduce impact
6. **Escalation path** — if the root cause cannot be identified from metrics alone
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
