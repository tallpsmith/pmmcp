"""MCP Prompt: session_init — Pre-register canonical derived metrics.

Instructs Claude to register three standard derived metrics at session start,
verify each via pcp_fetch_live, and report results without aborting.
"""

from __future__ import annotations

from pmmcp.server import mcp

# Canonical derived metric definitions — expressions and names
_DERIVED_METRICS = [
    (
        "derived.cpu.utilisation",
        "100 - rate(kernel.all.cpu.idle) / hinv.ncpu / 10",
        "CPU utilisation % (all non-idle states, cross-platform)",
    ),
    (
        "derived.disk.utilisation",
        "rate(disk.all.avactive) / 10",
        "Aggregate disk busy time % across all devices",
    ),
    (
        "derived.mem.utilisation",
        "100 * mem.util.used / mem.physmem",
        "Memory utilisation % (used / physical)",
    ),
]


def _session_init_impl(
    host: str | None = None,
    timerange: str | None = None,
) -> list[dict]:
    """Pure function returning the session_init prompt messages.

    Testable without MCP infrastructure.
    """
    host_clause = f" on host **{host}**" if host else " (all hosts)"
    timerange_clause = (
        f" for the window **{timerange}**" if timerange else " (default: last 1 hour)"
    )

    metric_lines = "\n".join(
        f"- `{name}` = `{expr}`  — {desc}" for name, expr, desc in _DERIVED_METRICS
    )

    metric_names = [name for name, _, _ in _DERIVED_METRICS]
    verify_lines = "\n".join(f'   - `pcp_fetch_live(names=["{name}"])`' for name in metric_names)

    content = f"""\
You are initialising a PCP monitoring session{host_clause}{timerange_clause}.

Register the following canonical derived metrics using `pcp_derive_metric`, \
then verify each is available with `pcp_fetch_live`. Report results without aborting \
if any metric fails — note failures and continue.

## Step 1 — Register Derived Metrics

Call `pcp_derive_metric` for each metric below:

{metric_lines}

Example call for the first metric:
```
pcp_derive_metric(
    name="derived.cpu.utilisation",
    expr="100 - rate(kernel.all.cpu.idle) / hinv.ncpu / 10"
)
```

Registration is idempotent — re-registering an existing name overwrites silently.

## Step 2 — Verify Availability

After registering, verify each derived metric is resolvable by calling `pcp_fetch_live`:

{verify_lines}

## Step 3 — Report Results

For each metric, report whether registration and verification succeeded or failed:

- **Success**: `derived.cpu.utilisation` registered and verified ✓
- **Failure**: `derived.disk.utilisation` failed verification — \
`disk.all.avactive` may not be available on this host. Note and continue.

**Do not abort if one or more verifications fail.** Report which metrics are available \
and which are not, so downstream investigations know which derived metrics can be used.
"""

    return [{"role": "user", "content": content}]


@mcp.prompt()
def session_init(
    host: str | None = None,
    timerange: str | None = None,
) -> list[dict]:
    """Pre-register canonical derived metrics and verify availability.

    Registers derived.cpu.utilisation, derived.disk.utilisation, and
    derived.mem.utilisation via pcp_derive_metric, then verifies each
    via pcp_fetch_live. Reports success/failure per metric without aborting.
    Call this at the start of any investigation session to ensure derived
    metrics are available for use.

    Args:
        host: Target host to verify metrics against (optional — all hosts if omitted)
        timerange: Time window hint for the session (optional)
    """
    return _session_init_impl(host, timerange)
