# Research: pcp_quick_investigate

**Feature**: 006-quick-investigate | **Date**: 2026-03-05

## R1: Orchestration Pattern — Composing Existing _impl Functions

**Decision**: Compose `_discover_metrics_impl` + `_detect_anomalies_impl` rather than reimplementing.

**Rationale**: Both functions already exist, are well-tested, and follow the injectable pattern. The new tool is a thin orchestrator that computes time windows, calls discovery, then feeds results into anomaly detection. This avoids duplicating ~200 lines of series fetching, stats computation, and z-score logic.

**Alternatives considered**:
- **Direct series API**: Would duplicate `_fetch_window` and `_compute_stats` logic from `_fetch.py` and `_stats.py`. Higher maintenance burden, more test surface.
- **Wrap `pcp_scan_changes`**: `pcp_scan_changes` uses ratio-based change detection, not z-score anomaly detection. Less precise for the "what's unusual?" question.
- **New pmproxy endpoint**: Out of scope — we work with the existing REST API.

## R2: Metric Discovery Approach

**Decision**: Use `_discover_metrics_impl` with `prefix` parameter for scoping.

**Rationale**: The existing discovery function handles both broad enumeration (`prefix=""`) and subsystem-scoped discovery (`prefix="disk"`). It uses the `/pmapi/children` endpoint which returns the metric tree structure. This is the same approach all other tools use for metric enumeration.

**Alternatives considered**:
- **Hardcoded metric lists**: Brittle, doesn't adapt to different PCP deployments.
- **`pcp_search` (full-text search)**: Better for fuzzy matching, but subsystem scoping is naturally a tree-prefix operation.
- **`series_query`**: Series-based discovery; adds Redis dependency and doesn't filter by subsystem naturally.

**Open question resolved**: Discovery may return hundreds of metrics. The anomaly detection step naturally filters to only those with significant z-scores, and the 50-result cap (FR-003) bounds the output. No pre-filtering of discovery results is needed.

## R3: Time Window Computation

**Decision**: Centre the recent window on `time_of_interest`, baseline ends where recent begins.

**Rationale**: When a user says "around 2pm", they mean a window centred on that time, not starting at that time. The baseline should not overlap the recent window to avoid contaminating the comparison.

**Computation**:
```
half_lookback = lookback / 2
recent_start = time_of_interest - half_lookback
recent_end   = time_of_interest + half_lookback
baseline_start = recent_start - baseline_days
baseline_end   = recent_start
```

**Alternatives considered**:
- **Window starting at time_of_interest**: Misses the "ramp up" before the event time.
- **Overlapping baseline**: Would reduce anomaly detection sensitivity.

## R4: Result Formatting

**Decision**: Structured JSON with typed fields per anomaly.

**Rationale**: The agent needs structured data to reason over (filter, sort, present). A pre-formatted text blob prevents the agent from doing its job. The `summary` field provides a ready-made sentence for quick display.

**Fields per result**: `metric`, `instance`, `score` (z-score), `severity` (categorical), `direction` (up/down), `magnitude` (numeric change), `summary` (human-readable sentence).

**Alternatives considered**:
- **Plain text only**: Loses structure, agent can't filter or sort.
- **Both JSON + text**: Over-engineering per Principle V.

## R5: Error Handling Strategy

**Decision**: Fail fast — propagate all errors via `_mcp_error()`.

**Rationale**: Silent fallback is exactly what caused the original problem (issue #19). When `pcp_detect_anomalies` failed, the agent fell back to raw `pcp_fetch_timeseries`. By failing clearly, we force the root cause to be addressed rather than hidden.

**Alternatives considered**:
- **Degrade to `pcp_scan_changes`**: Creates a different silent-fallback problem.
- **Partial results**: Complicates the return type and trust model.

## R6: Tool Description Wording

**Decision**: Add steering language to existing tool descriptions without changing their parameters or behaviour.

**Rationale**: Tool descriptions are the primary mechanism agents use for tool selection. By adding "For open-ended investigation, start with `pcp_quick_investigate`" to confirmation tools, and "NOT for exploratory investigation" to `pcp_fetch_timeseries`, we create a clear decision tree in the agent's context.

**Best practice**: Keep additions concise (1 sentence each). Don't remove existing description content — only append steering guidance.
