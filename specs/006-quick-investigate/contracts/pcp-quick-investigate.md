# Contract: pcp_quick_investigate

**Feature**: 006-quick-investigate | **Date**: 2026-03-05

## MCP Tool Registration

The tool MUST be discoverable via `mcp.list_tools()` with the following metadata:

| Property | Value |
|----------|-------|
| Name | `pcp_quick_investigate` |
| Module | `src/pmmcp/tools/investigate.py` |
| Registration | Side-effect import via `tools/__init__.py` |

## Parameters

```json
{
  "type": "object",
  "properties": {
    "time_of_interest": {
      "type": "string",
      "description": "When to investigate — ISO-8601 datetime or relative expression like '-2hours'. This is the centre point of the analysis window."
    },
    "subsystem": {
      "type": "string",
      "default": "",
      "description": "Optional metric prefix to scope investigation (e.g., 'disk', 'network', 'kernel'). Empty = all metrics."
    },
    "lookback": {
      "type": "string",
      "default": "2hours",
      "description": "Width of the comparison window centred on time_of_interest. Use PCP time format (e.g., '30minutes', '2hours')."
    },
    "baseline_days": {
      "type": "integer",
      "default": 7,
      "description": "Number of days before the comparison window to use as the baseline for anomaly detection."
    },
    "host": {
      "type": "string",
      "default": "",
      "description": "Target host. Empty = default pmproxy host."
    }
  },
  "required": ["time_of_interest"]
}
```

## Success Response

```json
{
  "anomalies": [
    {
      "metric": "kernel.all.load",
      "instance": "1 minute",
      "score": 3.45,
      "severity": "high",
      "direction": "up",
      "magnitude": 2.1,
      "summary": "Load average 1-min is 3.5σ above baseline mean (0.8 → 2.9)"
    }
  ],
  "metadata": {
    "time_of_interest": "2025-01-15T14:00:00",
    "recent_window": ["2025-01-15T13:00:00", "2025-01-15T15:00:00"],
    "baseline_window": ["2025-01-08T13:00:00", "2025-01-15T13:00:00"],
    "metrics_examined": 42,
    "host": "localhost"
  },
  "message": "Found 5 anomalies across 42 metrics examined",
  "truncated": false
}
```

## Empty Response (no anomalies)

```json
{
  "anomalies": [],
  "metadata": {
    "time_of_interest": "2025-01-15T14:00:00",
    "recent_window": ["2025-01-15T13:00:00", "2025-01-15T15:00:00"],
    "baseline_window": ["2025-01-08T13:00:00", "2025-01-15T13:00:00"],
    "metrics_examined": 42,
    "host": "localhost"
  },
  "message": "No anomalies detected across 42 metrics examined",
  "truncated": false
}
```

## Error Responses

All errors use the standard `_mcp_error()` format:

### Future timestamp
```json
{
  "content": [{"type": "text", "text": "Error: Validation error\n\nDetails: time_of_interest must be in the past\nSuggestion: Provide a historical timestamp to investigate."}],
  "isError": true
}
```

### Connection failure
```json
{
  "content": [{"type": "text", "text": "Error: Connection error\n\nDetails: Cannot connect to pmproxy at http://localhost:44322\nSuggestion: Check that pmproxy is running and accessible."}],
  "isError": true
}
```

### No metrics found
```json
{
  "content": [{"type": "text", "text": "Error: No metrics found\n\nDetails: No metrics discovered for prefix 'nonexistent'\nSuggestion: Check the subsystem name or omit it to search all metrics."}],
  "isError": true
}
```

## Invariants

1. `anomalies` list MUST contain at most 50 items
2. `anomalies` MUST be sorted by `score` descending
3. `truncated` MUST be `true` if and only if the pre-cap result count exceeded 50
4. `metadata.metrics_examined` MUST reflect the actual number of metrics passed to anomaly detection
5. All `score` values MUST be >= 0 (absolute z-scores)
6. `severity` MUST be one of: "low", "medium", "high" (no "none" — items with no anomaly are excluded)
7. `direction` MUST be one of: "up", "down"

## Tool Description Contract

The following tools MUST include steering language in their descriptions:

| Tool | Required text (or equivalent) |
|------|-------------------------------|
| `pcp_quick_investigate` | "Start here for open-ended investigation. Only requires a time of interest." |
| `pcp_detect_anomalies` | "For targeted anomaly analysis on known metrics. For discovery, start with pcp_quick_investigate." |
| `pcp_compare_windows` | "For comparing specific metrics across known windows. For discovery, start with pcp_quick_investigate." |
| `pcp_scan_changes` | "For scanning broad changes in a metric prefix. For discovery, start with pcp_quick_investigate." |
| `pcp_fetch_timeseries` | "For targeted retrieval of a specific metric. NOT for exploratory investigation." |

## Prompt Update Contract

The `investigate_subsystem` prompt MUST include a tool-ordering workflow section:
1. Start with `pcp_quick_investigate` for broad discovery
2. Confirm findings with `pcp_detect_anomalies` or `pcp_compare_windows`
3. Retrieve detailed data with `pcp_fetch_timeseries` only for identified metrics
