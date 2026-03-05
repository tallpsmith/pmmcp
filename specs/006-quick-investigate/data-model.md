# Data Model: pcp_quick_investigate

**Feature**: 006-quick-investigate | **Date**: 2026-03-05

## Entities

### InvestigationRequest (Input)

Tool parameters — not a persisted entity.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `time_of_interest` | `str` | Yes | — | ISO-8601 datetime or PCP relative expression (e.g., "-2hours") |
| `subsystem` | `str` | No | `""` | Metric prefix filter (e.g., "disk", "network", "kernel") |
| `lookback` | `str` | No | `"2hours"` | Width of the comparison window centred on `time_of_interest` |
| `baseline_days` | `int` | No | `7` | Number of days before the comparison window to use as baseline |
| `host` | `str` | No | `""` | Target host (empty = default pmproxy host) |

**Validation rules**:
- `time_of_interest` MUST parse to a datetime in the past (reject future timestamps)
- `lookback` MUST be a valid PCP time expression (e.g., "30minutes", "2hours", "1day")
- `baseline_days` MUST be >= 1
- `subsystem` is free-form text matched as a metric name prefix

### AnomalySummaryItem (Output)

One item per anomalous metric/instance pair. Returned as a JSON object.

| Field | Type | Description |
|-------|------|-------------|
| `metric` | `str` | Full metric name (e.g., "kernel.all.load") |
| `instance` | `str` | Instance name (e.g., "1 minute") or empty string for singular metrics |
| `score` | `float` | Absolute z-score (higher = more anomalous) |
| `severity` | `str` | Categorical: "low" (\|z\| 2-3), "medium" (\|z\| 3-4), "high" (\|z\| > 4) |
| `direction` | `str` | "up" or "down" — direction of change vs baseline |
| `magnitude` | `float` | Absolute difference between recent mean and baseline mean |
| `summary` | `str` | Human-readable sentence, e.g., "Load average 1-min is 3.5σ above baseline mean (0.8 → 2.9)" |

**Ordering**: Descending by `score` (most anomalous first).

**Cardinality**: At most 50 items (FR-003).

### InvestigationResult (Wrapper)

Top-level response structure returned by the tool.

| Field | Type | Description |
|-------|------|-------------|
| `anomalies` | `list[AnomalySummaryItem]` | Ranked anomaly list (0 to 50 items) |
| `metadata` | `dict` | Investigation parameters used: `time_of_interest`, `recent_window`, `baseline_window`, `metrics_examined`, `host` |
| `message` | `str` | Status message: "Found N anomalies across M metrics" or "No anomalies detected" |
| `truncated` | `bool` | `true` if results were capped at 50 |

## Relationships

```
InvestigationRequest
    │
    ├── (1) pcp_discover_metrics(prefix=subsystem)
    │       └── returns: list of metric names
    │
    └── (2) pcp_detect_anomalies(metrics=discovered, recent_window, baseline_window)
            └── returns: list of anomalies
                    │
                    └── (3) sort + cap → list[AnomalySummaryItem]
                            │
                            └── InvestigationResult
```

## State Transitions

N/A — stateless tool. Each call is independent. No persistence, no caching, no side effects.
