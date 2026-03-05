# Data Model: Investigation UX Improvements

**Feature**: 005-investigation-ux

This feature introduces no new data storage and no schema changes. All changes are to
MCP prompt text and tool docstrings. The "entities" here are the new/modified MCP
interface surfaces.

---

## New MCP Prompt: `session_init`

**Module**: `src/pmmcp/prompts/session_init.py`

### Signature

```python
def session_init(
    host: str | None = None,
    timerange: str | None = None,
) -> list[dict]:
```

### Return Shape

```python
[{"role": "user", "content": "<instructional text>"}]
```

### Derived Metric Definitions

| Name | Expression | Measures |
|------|-----------|---------|
| `derived.cpu.utilisation` | `100 - rate(kernel.all.cpu.idle) / hinv.ncpu / 10` | CPU utilisation % (all non-idle states) |
| `derived.disk.utilisation` | `rate(disk.all.avactive) / 10` | Aggregate disk busy % |
| `derived.mem.utilisation` | `100 * mem.util.used / mem.physmem` | Used memory as % of physical RAM |

### Instructional Content Structure

The returned prompt content instructs Claude to:

1. Call `pcp_derive_metric` for each of the three derived metrics (name + expression)
2. Call `pcp_fetch_live` for each derived metric name to verify availability
3. Report which metrics are available and which failed (without aborting)

### Idempotency

Re-registration is unconditional — `pcp_derive_metric` silently overwrites. No guard logic.

---

## Modified MCP Prompt: `incident_triage`

**Module**: `src/pmmcp/prompts/triage.py` (full rewrite)

### Signature (unchanged)

```python
def incident_triage(
    symptom: str,
    host: str | None = None,
    timerange: str | None = None,
) -> list[dict]:
```

### New Content Structure (4-Step Spine)

| Step | Tool | Advancement Criterion |
|------|------|-----------------------|
| 1. Anomaly Detection | `pcp_detect_anomalies` | If anomalies found (any severity), advance to Step 2 |
| 2. Window Comparison | `pcp_compare_windows` | If significant delta (>2 stddev), advance to Step 3 |
| 3. Change Scanning | `pcp_scan_changes` | If changed metrics identified, advance to Step 4 |
| 4. Targeted Drilldown | `pcp_fetch_timeseries` | On changed/anomalous metrics only |

**Preserved from old prompt** (required by existing passing tests):
- Symptom/host/timerange interpolation
- Guard clauses: missing-tool abort, out-of-retention stop
- Symptom-to-subsystem mapping table
- Fleet-wide vs host-specific scope check

---

## Modified Tool Descriptions

### `pcp_detect_anomalies` (anomaly.py)

Add to opening description: "**Start here.** This is the recommended first tool at the
start of any investigation..."

### `pcp_fetch_timeseries` (timeseries.py)

Add to description: "Use this for targeted drill-down after anomalies are identified
via `pcp_detect_anomalies`. Not a general starting point for investigation."

### Tools with `limit` guidance (all tools accepting user-supplied `limit`)

| Tool | Param | Current Default | Guidance to Add |
|------|-------|----------------|----------------|
| `pcp_fetch_timeseries` | `limit` | 500 | Exploration: 50. Analysis: increase as needed. |
| `pcp_query_series` | `limit` | 500 | Exploration: 50. Analysis: increase as needed. |
| `pcp_discover_metrics` | `limit` | 50 | Exploration: 50. Analysis: increase to 200+. |
| `pcp_get_hosts` | `limit` | 50 | Exploration: 50. Analysis: increase as needed. |
| `pcp_search` | `limit` | 20 | Exploration: 50. Full corpus: increase to 100+. |
| `pcp_scan_changes` | `max_metrics` | 50 | Exploration: 50. Full scan: increase to 200+. |
