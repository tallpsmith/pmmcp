# MCP Tool Contracts: pmmcp

**Feature**: 001-pcp-mcp-service
**Date**: 2026-02-21
**MCP Server Name**: `pmmcp`
**MCP Server Version**: `0.1.0`

## Tool 1: pcp_get_hosts

**Description**: List all monitored hosts visible to the pmproxy instance. Use this first to understand what infrastructure is available before querying metrics.

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "match": {
      "type": "string",
      "description": "Glob pattern to filter hostnames (e.g., 'web-*')",
      "default": ""
    },
    "limit": {
      "type": "integer",
      "description": "Maximum number of hosts to return",
      "default": 50,
      "minimum": 1,
      "maximum": 1000
    },
    "offset": {
      "type": "integer",
      "description": "Pagination offset",
      "default": 0,
      "minimum": 0
    }
  }
}
```

**Output**: `PaginatedResponse<Host>` — list of hosts with source IDs, hostnames, and labels.

**pmproxy endpoints**: `GET /series/sources`

**User stories**: US1, US2

---

## Tool 2: pcp_discover_metrics

**Description**: Browse the metric namespace tree or search for metrics by keyword. Returns metric names with one-line descriptions. Use this to find which metrics exist before fetching their values. Supply either `prefix` for tree browsing or `search` for full-text search — not both.

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "host": {
      "type": "string",
      "description": "Target hostname. Empty uses the default pmproxy host.",
      "default": ""
    },
    "prefix": {
      "type": "string",
      "description": "Metric namespace prefix to browse children of (e.g., 'kernel.percpu'). Mutually exclusive with 'search'.",
      "default": ""
    },
    "search": {
      "type": "string",
      "description": "Full-text search query across metric names and descriptions (e.g., 'cpu utilization'). Mutually exclusive with 'prefix'.",
      "default": ""
    },
    "limit": {
      "type": "integer",
      "description": "Maximum number of metrics to return",
      "default": 50,
      "minimum": 1,
      "maximum": 1000
    },
    "offset": {
      "type": "integer",
      "description": "Pagination offset",
      "default": 0,
      "minimum": 0
    }
  }
}
```

**Output**: `PaginatedResponse<{ name: string, oneline: string, leaf: boolean }>` — metric names with descriptions and whether they are leaf nodes (have values) or branches (have children).

**pmproxy endpoints**: `GET /pmapi/children` (tree browsing), `GET /search/text` (keyword search), `GET /search/suggest` (autocomplete)

**User stories**: US1, US2

---

## Tool 3: pcp_get_metric_info

**Description**: Get detailed metadata for one or more specific metrics: full help text, type, units, semantics, instance domain members, and labels. Use this to understand what a metric measures before interpreting its values.

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "names": {
      "type": "array",
      "items": { "type": "string" },
      "description": "List of fully-qualified metric names (e.g., ['kernel.percpu.cpu.user', 'mem.util.free'])",
      "minItems": 1,
      "maxItems": 50
    },
    "host": {
      "type": "string",
      "description": "Target hostname. Empty uses the default pmproxy host.",
      "default": ""
    }
  },
  "required": ["names"]
}
```

**Output**: `Metric[]` — full metadata for each requested metric including help text, type, units, semantics, instance domain members, and labels.

**pmproxy endpoints**: `GET /pmapi/metric`, `GET /pmapi/indom`

**User stories**: US1, US2, US3

---

## Tool 4: pcp_fetch_live

**Description**: Fetch current (real-time) values for one or more metrics from a live host. Returns the most recent sample for each metric and instance. Use this for point-in-time checks and live monitoring snapshots.

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "names": {
      "type": "array",
      "items": { "type": "string" },
      "description": "List of metric names to fetch",
      "minItems": 1,
      "maxItems": 100
    },
    "host": {
      "type": "string",
      "description": "Target hostname",
      "default": ""
    },
    "instances": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Filter to specific instances (e.g., ['sda', 'sdb']). Empty means all instances.",
      "default": []
    }
  },
  "required": ["names"]
}
```

**Output**: `{ timestamp: string, values: { name: string, instances: { instance: string, value: number | string }[] }[] }` — current values for each metric and instance.

**pmproxy endpoints**: `GET /pmapi/context`, `GET /pmapi/fetch`, `GET /pmapi/profile`

**User stories**: US1, US2

---

## Tool 5: pcp_fetch_timeseries

**Description**: Fetch historical time-series values for one or more metrics over a time window. Returns timestamped samples. Supports the hierarchical sampling strategy: start with wide windows and coarse intervals, then drill down to interesting periods at finer granularity. The 'auto' interval selects granularity based on window size.

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "names": {
      "type": "array",
      "items": { "type": "string" },
      "description": "List of metric names",
      "minItems": 1,
      "maxItems": 50
    },
    "start": {
      "type": "string",
      "description": "Start time. ISO-8601 datetime or PCP relative expression (e.g., '-6hours', '-7days')",
      "default": "-1hour"
    },
    "end": {
      "type": "string",
      "description": "End time. Same format as start.",
      "default": "now"
    },
    "interval": {
      "type": "string",
      "description": "Sampling interval (e.g., '15s', '1min', '5min', '1hour'). 'auto' selects based on window size.",
      "default": "auto"
    },
    "host": {
      "type": "string",
      "description": "Target hostname or glob pattern (e.g., 'web-*'). Empty queries all hosts.",
      "default": ""
    },
    "instances": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Filter to specific instances. Empty means all.",
      "default": []
    },
    "limit": {
      "type": "integer",
      "description": "Maximum data points per metric/instance combination",
      "default": 500,
      "minimum": 1,
      "maximum": 5000
    },
    "offset": {
      "type": "integer",
      "description": "Pagination offset for data points",
      "default": 0,
      "minimum": 0
    },
    "zone": {
      "type": "string",
      "description": "Timezone for timestamps",
      "default": "UTC"
    }
  },
  "required": ["names"]
}
```

**Output**: `PaginatedResponse<{ name: string, instance?: string, samples: { timestamp: string, value: number | string }[] }>` — time-series data grouped by metric and instance.

**Auto-interval mapping**: ≤1h → 15s, ≤24h → 5min, ≤7d → 1hour, >7d → 6hour

**pmproxy endpoints**: `GET /series/query`, `GET /series/values`, `GET /series/instances`

**User stories**: US1, US3, US4

---

## Tool 6: pcp_query_series

**Description**: Execute a raw PCP series query expression for advanced filtering. The query language supports label matching, arithmetic, and aggregation. Use this when the AI agent needs precise control over series selection beyond what pcp_fetch_timeseries provides (e.g., label-based filtering like 'kernel.percpu.cpu.user{hostname=="web-01"}').

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "expr": {
      "type": "string",
      "description": "PCP series query expression"
    },
    "start": {
      "type": "string",
      "description": "Start time",
      "default": "-1hour"
    },
    "end": {
      "type": "string",
      "description": "End time",
      "default": "now"
    },
    "interval": {
      "type": "string",
      "description": "Sampling interval",
      "default": "auto"
    },
    "limit": {
      "type": "integer",
      "description": "Max data points per series",
      "default": 500,
      "minimum": 1,
      "maximum": 5000
    },
    "offset": {
      "type": "integer",
      "description": "Pagination offset",
      "default": 0,
      "minimum": 0
    }
  },
  "required": ["expr"]
}
```

**Output**: Same as `pcp_fetch_timeseries`.

**pmproxy endpoints**: `GET /series/query`, `GET /series/values`, `GET /series/descs`, `GET /series/instances`, `GET /series/labels`

**User stories**: US1, US3, US4

---

## Tool 7: pcp_compare_windows

**Description**: Fetch the same set of metrics over two different time windows and return summary statistics (mean, min, max, p95, stddev) for each window with computed deltas. Designed for "good period vs bad period" comparison. The AI agent interprets the statistical differences to identify significant changes.

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "names": {
      "type": "array",
      "items": { "type": "string" },
      "description": "List of metric names to compare",
      "minItems": 1,
      "maxItems": 50
    },
    "window_a_start": {
      "type": "string",
      "description": "Start of first (baseline/good) window"
    },
    "window_a_end": {
      "type": "string",
      "description": "End of first window"
    },
    "window_b_start": {
      "type": "string",
      "description": "Start of second (comparison/bad) window"
    },
    "window_b_end": {
      "type": "string",
      "description": "End of second window"
    },
    "host": {
      "type": "string",
      "description": "Target hostname",
      "default": ""
    },
    "instances": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Filter to specific instances",
      "default": []
    },
    "interval": {
      "type": "string",
      "description": "Sampling interval for both windows",
      "default": "auto"
    },
    "include_samples": {
      "type": "boolean",
      "description": "If true, include raw sample data in addition to summary stats",
      "default": false
    }
  },
  "required": ["names", "window_a_start", "window_a_end", "window_b_start", "window_b_end"]
}
```

**Output**: `WindowComparison[]` — per-metric/instance comparison with summary stats for each window, absolute and percentage deltas, and significance flag (> 2 stddev).

**pmproxy endpoints**: `GET /series/query`, `GET /series/values` (called twice)

**User stories**: US3, US4

---

## Tool 8: pcp_search

**Description**: Full-text search across all metric names, help text, instance domains, and labels indexed by pmproxy. Returns ranked results. Use this when the AI agent needs to find metrics related to a concept (e.g., 'disk latency', 'network errors') without knowing exact PCP metric names.

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "description": "Free-text search query"
    },
    "type": {
      "type": "string",
      "description": "Result type filter",
      "enum": ["all", "metric", "indom", "instance"],
      "default": "all"
    },
    "limit": {
      "type": "integer",
      "description": "Maximum results",
      "default": 20,
      "minimum": 1,
      "maximum": 100
    },
    "offset": {
      "type": "integer",
      "description": "Pagination offset",
      "default": 0,
      "minimum": 0
    }
  },
  "required": ["query"]
}
```

**Output**: `PaginatedResponse<SearchResult>` — ranked search results with name, type, description, and relevance score.

**pmproxy endpoints**: `GET /search/text`, `GET /search/suggest`

**User stories**: US1, US2

---

## Tool 9: pcp_derive_metric

**Description**: Create a derived (computed) metric on-the-fly using PCP's derived metric expression syntax. This allows the AI agent to define custom ratios, rates, or aggregations (e.g., total CPU utilisation percentage). Derived metrics can then be fetched like any other metric using pcp_fetch_live or pcp_fetch_timeseries.

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "description": "Name for the derived metric (e.g., 'derived.cpu.total_util')"
    },
    "expr": {
      "type": "string",
      "description": "PCP derived metric expression (e.g., '100 * (kernel.all.cpu.user + kernel.all.cpu.sys) / hinv.ncpu')"
    },
    "host": {
      "type": "string",
      "description": "Target hostname for the context",
      "default": ""
    }
  },
  "required": ["name", "expr"]
}
```

**Output**: `{ success: boolean, name: string, message: string }` — confirmation of derived metric creation.

**pmproxy endpoints**: `GET /pmapi/derive`, `GET /pmapi/context`

**User stories**: US1, US3, US4

---

## Error Response Format

All tools return errors in a consistent format:

```json
{
  "content": [{
    "type": "text",
    "text": "Error: <human-readable description>\n\nDetails: <specific issue>\nSuggestion: <what the user or agent can try>"
  }],
  "isError": true
}
```

Error categories:
- **Connection error**: pmproxy unreachable — includes URL attempted and suggestion to check connectivity.
- **Not found**: Metric or host not found — includes the name queried and suggests using `pcp_discover_metrics` or `pcp_search`.
- **Invalid parameters**: Bad input — includes which parameter failed validation and expected format.
- **Timeout**: pmproxy took too long — includes timeout value and suggests reducing scope (fewer metrics, smaller time window).
- **pmproxy error**: Upstream error from pmproxy — includes the raw error message wrapped in context.
