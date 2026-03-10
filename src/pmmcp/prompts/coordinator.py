"""MCP Prompt: coordinate_investigation — Parallel specialist dispatch + synthesis.

Instructs the LLM to dispatch all 6 specialist sub-agents concurrently (or
sequentially as fallback), then synthesise findings into a unified root-cause
narrative with cross-subsystem correlation.
"""

from __future__ import annotations

from pmmcp.prompts.specialist import _SPECIALIST_KNOWLEDGE
from pmmcp.server import mcp

_SUBSYSTEM_ORDER = ["cpu", "memory", "disk", "network", "process", "crosscutting"]


def _coordinate_investigation_impl(
    request: str,
    host: str | None = None,
    time_of_interest: str | None = None,
    lookback: str | None = None,
) -> list[dict]:
    """Pure function returning the coordinate_investigation prompt messages.

    Testable without MCP infrastructure.
    """
    host_clause = f" on host **{host}**" if host else " across all monitored hosts"
    time_clause = f" centred on **{time_of_interest}**" if time_of_interest else ""
    lookback_clause = f" (lookback: **{lookback}**)" if lookback else ""

    # Build dispatch table for all specialists
    dispatch_lines = []
    for sub in _SUBSYSTEM_ORDER:
        entry = _SPECIALIST_KNOWLEDGE[sub]
        display = entry["display_name"]
        args = f'subsystem="{sub}"'
        if request:
            args += f', request="{request}"'
        if host:
            args += f', host="{host}"'
        if time_of_interest:
            args += f', time_of_interest="{time_of_interest}"'
        if lookback:
            args += f', lookback="{lookback}"'
        dispatch_lines.append(f"- **{display}**: `specialist_investigate({args})`")

    dispatch_table = "\n".join(dispatch_lines)

    content = f"""\
You are coordinating a **broad performance investigation**{host_clause}{time_clause}\
{lookback_clause}.

**Investigation request**: {request}

## Phase 1 — Specialist Dispatch

Invoke the `specialist_investigate` prompt for each of the 6 subsystems below. \
Each specialist carries deep domain knowledge and will report structured findings.

{dispatch_table}

### Parallel Mode (preferred)

If your environment supports sub-agents or parallel tool invocation, dispatch ALL 6 \
specialists concurrently. This is the fastest path to a comprehensive picture.

### Sequential Fallback

If parallel dispatch is not available, invoke each specialist sequentially in the \
order listed above. CPU → Memory → Disk → Network → Process → Cross-cutting. \
This order follows the most common dependency chain.

### Handling Failures

Some specialists may fail or return no data (e.g., no metrics available for that \
subsystem, pmproxy connectivity issues, or partial data). This is expected — not \
every subsystem will have anomalies.

- **Continue** with the remaining specialists even if one fails.
- **Note** which specialists returned no data or failed — this is useful context.
- A specialist reporting "no anomalies found" is a valid and valuable result.

## Phase 2 — Synthesis

After all specialists have reported (or failed), synthesise their findings:

1. **Cross-reference** findings across subsystems. Look for correlations:
   - CPU iowait + disk saturation → disk is the root cause, not CPU
   - Memory pressure + swap activity + disk I/O → memory leak causing cascade
   - Network retransmits + CPU sys spike → possible interrupt storm

2. **Timeline correlation**: Identify when the problem started across all subsystems. \
   The subsystem that changed first is likely the root cause.

3. **Build a unified narrative**: Don't just list findings per subsystem — tell the \
   story of what happened. "At 14:32, memory utilisation crossed 95%, triggering swap \
   activity, which caused disk I/O to spike, which manifested as CPU iowait."

4. **Rank by classification, then severity**: Group findings by classification tier, \
   not by subsystem. ANOMALY findings rank above RECURRING, which rank above BASELINE — \
   regardless of severity. Within each tier, sort by severity (critical → warning → info). \
   What changed (ANOMALY) is more actionable than what has always been wrong (BASELINE).

5. **Call out normal behaviour**: Explicitly identify findings that are baseline \
   behaviour — chronic conditions that are normal for this host. These still matter \
   (a host whose "normal" is CPU-saturated is sick), but they are not the trigger \
   for the current incident.

6. **Highlight recurring patterns**: When an apparent anomaly matches a known \
   recurring pattern (RECURRING classification from specialists), call this out — \
   "this spike looks alarming but occurs daily at 2am during the backup window."

7. **Recommend actions**: Concrete next steps — not "investigate further" but \
   "check process X for memory leak" or "increase swap space as immediate mitigation."

## Output Structure

```
## Investigation Summary
<1-2 sentence executive summary>

## Root Cause Analysis
<unified narrative with timeline and cross-subsystem correlation>

## Findings by Classification & Severity

### New Anomalies
1. [CRITICAL] ...
2. [WARNING] ...

### Recurring Patterns
1. [WARNING] ... (occurs daily at <time>)

### Baseline Behaviour (Chronic Conditions)
1. [WARNING] ... (has been this way for 7+ days — not a new problem)

### Normal Operation
- <subsystem>: no anomalies detected

## Recommendations
1. Immediate: ...
2. Short-term: ...
3. Long-term: ...

## Specialist Status
- CPU: <completed | no anomalies | failed: reason>
- Memory: ...
- Disk: ...
- Network: ...
- Process: ...
- Cross-cutting: ...
```
"""

    return [{"role": "user", "content": content}]


@mcp.prompt()
def coordinate_investigation(
    request: str,
    host: str | None = None,
    time_of_interest: str | None = None,
    lookback: str | None = None,
) -> list[dict]:
    """Coordinate a broad performance investigation using 6 specialist sub-agents.

    Dispatches specialist_investigate for cpu, memory, disk, network, process,
    and crosscutting subsystems — either in parallel (preferred) or sequentially.
    Then synthesises findings into a unified root-cause narrative with
    cross-subsystem correlation.

    Args:
        request: What to investigate (e.g., "the app is slow") — required
        host: Target host (all hosts if omitted) — optional
        time_of_interest: Centre of investigation window (default: now) — optional
        lookback: Window size around time_of_interest (default: 2hours) — optional
    """
    return _coordinate_investigation_impl(request, host, time_of_interest, lookback)
