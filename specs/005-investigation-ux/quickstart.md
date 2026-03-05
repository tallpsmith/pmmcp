# Quickstart: Investigation UX Improvements

**Feature**: 005-investigation-ux

---

## New: Session Initialisation

At the start of any investigation session, invoke the `session_init` prompt. This
pre-registers three standard derived metrics so they are immediately available for
all subsequent tool calls — without manual `pcp_derive_metric` calls.

**Claude Code invocation**:
```
Use the session_init prompt to start this investigation.
```

**What happens**:
1. Claude registers `derived.cpu.utilisation`, `derived.disk.utilisation`, and `derived.mem.utilisation`
2. Claude verifies each with `pcp_fetch_live` and reports which are available
3. Investigation proceeds with the derived metrics ready to use

**With a specific host**:
```
Use the session_init prompt for host web-prod-01
```

---

## Improved: Incident Triage Workflow

The `incident_triage` prompt now prescribes a four-step investigation sequence:

| Step | Tool | Purpose |
|------|------|---------|
| 1 | `pcp_detect_anomalies` | Identify which metrics deviate from baseline |
| 2 | `pcp_compare_windows` | Quantify the delta between good and bad windows |
| 3 | `pcp_scan_changes` | Scan the metric namespace for anything else that changed |
| 4 | `pcp_fetch_timeseries` | Drill into specific metrics confirmed as anomalous |

**Invocation**:
```
Invoke incident_triage with symptom: "API response times doubled since 14:00"
```

---

## Tool Selection Guidance

### Start investigations with `pcp_detect_anomalies`

This tool is the recommended starting point. It compares recent behaviour against a
historical baseline and surfaces z-score deviations. Use it first.

### Use `pcp_fetch_timeseries` for drill-down

After `pcp_detect_anomalies` identifies anomalous metrics, use `pcp_fetch_timeseries`
to examine their full time-series at the granularity you need. Do not start here.

### Choosing a `limit` value

For initial exploration, use `limit=50` (the exploration default). Increase it only
when you need a complete dataset for analysis — and state your reason.

---

## Running the Tests

```bash
uv sync --extra dev

# All unit tests (includes new session_init + updated triage + tool description tests)
uv run pytest tests/unit/ --cov=pmmcp --cov-report=term-missing

# Just the new/changed tests
uv run pytest tests/unit/test_prompts_session_init.py \
              tests/unit/test_prompts_triage.py \
              tests/unit/test_tool_descriptions_ux.py -v
```
