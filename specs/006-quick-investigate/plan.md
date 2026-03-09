# Implementation Plan: Low-Friction Open-Ended Investigation Entry Point

**Branch**: `006-quick-investigate` | **Date**: 2026-03-05 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/006-quick-investigate/spec.md`

## Summary

Add `pcp_quick_investigate` — a single-call investigation entry point that accepts only a `time_of_interest` and returns a ranked anomaly summary. The tool dynamically discovers available metrics via `pcp_discover_metrics`, computes comparison and baseline windows from smart defaults, then delegates to `pcp_detect_anomalies` for z-score analysis. Complementary changes update tool descriptions and the `investigate_subsystem` prompt to steer agents toward summary tools before raw fetches.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: `mcp[cli]` >=1.2.0 (FastMCP), `pydantic` v2.x, `httpx` >=0.27
**Storage**: N/A — stateless tool; no persistence
**Testing**: `pytest`, `pytest-asyncio`, `respx` (httpx mocking), `ruff` (lint/format)
**Target Platform**: macOS (dev), Linux (CI/production)
**Project Type**: Single Python package (`src/pmmcp/`)
**Performance Goals**: Same latency envelope as existing `pcp_detect_anomalies` (SC-004); no extra round-trips beyond discovery + anomaly detection
**Constraints**: Output capped at 50 results (FR-003); token reduction >=70% vs raw fetch pattern (SC-003)
**Scale/Scope**: 1 new tool module, 3-5 existing tool description updates, 1 prompt update

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes / Justification |
|-----------|--------|----------------------|
| I. Code Quality — linting enforced, single-responsibility, complexity <= 10, peer review | PASS | New module follows existing `_*_impl()` pattern; ruff enforced; single tool per module |
| II. Testing Standards — TDD cycle, >= 80% unit coverage, contract tests on interface changes | PASS | TDD mandatory per constitution; unit tests with respx mocking; contract test for new tool registration |
| III. UX Consistency — design system adherence, WCAG 2.1 AA, actionable error messages | PASS | Error messages use `_mcp_error()` pattern; actionable suggestions included; no UI components |
| IV. Performance — latency SLA defined, performance budget in CI, profiling before optimization | PASS | SC-004 defines latency envelope (match `pcp_detect_anomalies`); no extra round-trips; 50-result cap prevents token explosion |
| V. Simplicity — YAGNI posture, no speculative abstractions, complexity justified below | PASS | Orchestration composes existing tools; no new abstractions; no speculative features |

## Project Structure

### Documentation (this feature)

```text
specs/006-quick-investigate/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── pcp-quick-investigate.md
└── tasks.md             # Phase 2 output (via /speckit.tasks)
```

### Source Code (repository root)

```text
src/pmmcp/
├── tools/
│   ├── __init__.py          # ADD: import investigate
│   ├── investigate.py       # NEW: pcp_quick_investigate + _quick_investigate_impl
│   ├── anomaly.py           # EDIT: update tool description (FR-005)
│   ├── comparison.py        # EDIT: update tool description (FR-005)
│   ├── scanning.py          # EDIT: update tool description (FR-005)
│   └── timeseries.py        # EDIT: update tool description (FR-007)
├── prompts/
│   └── investigate.py       # EDIT: update prompt guidance (FR-008)
└── models.py                # ADD: InvestigationRequest, AnomalySummaryItem (if needed)

tests/
├── unit/
│   └── test_investigate.py  # NEW: unit tests for _quick_investigate_impl
└── contract/
    └── test_tool_registration.py  # EDIT: add pcp_quick_investigate to tool list
```

**Structure Decision**: Follows existing single-package layout. New tool gets its own module (`tools/investigate.py`) per clarification, with side-effect import in `tools/__init__.py`. No new packages or architectural layers.

## Complexity Tracking

No violations to justify. All changes follow existing patterns.

## Design Decisions

### D1: Orchestration Strategy — Compose Existing _impl Functions

The new tool composes `_discover_metrics_impl` and `_detect_anomalies_impl` rather than reimplementing their logic. This keeps the tool as a thin orchestrator.

**Flow**:
1. Parse `time_of_interest` → `datetime`
2. Validate not in the future
3. Compute `recent_start`, `recent_end` from lookback (centred on `time_of_interest`)
4. Compute `baseline_start`, `baseline_end` from `baseline_days` (ending at `recent_start`)
5. Call `_discover_metrics_impl(client, prefix=subsystem)` to get metric names
6. Call `_detect_anomalies_impl(client, metrics=discovered_names, recent_start, recent_end, baseline_start, baseline_end)`
7. Sort by severity/z_score descending, cap at 50
8. Return structured JSON list

**Rationale**: Maximises code reuse, keeps orchestrator complexity low (~15 lines of logic), and ensures anomaly detection improvements automatically benefit this tool.

**Alternatives rejected**:
- Direct series API calls: duplicates `_fetch_window` + `_compute_stats` logic
- `pcp_scan_changes` wrapper: less precise than z-score anomaly detection

### D2: Time Window Computation

Given `time_of_interest` and `lookback` (default 2 hours):
- **Recent window**: `[time_of_interest - lookback/2, time_of_interest + lookback/2]`
- **Baseline window**: `[time_of_interest - baseline_days - lookback/2, time_of_interest - lookback/2]`

The recent window is centred on the time of interest. The baseline ends where the recent window begins — no overlap.

### D3: Metric Discovery Scope

- No subsystem filter: `_discover_metrics_impl(client, prefix="")` — returns all top-level metrics
- With subsystem filter: `_discover_metrics_impl(client, prefix=subsystem)` — e.g., `prefix="disk"` returns `disk.*` metrics
- Discovery results may be large; we pass the discovered list directly to anomaly detection which handles the per-metric analysis

### D4: Result Structure

Each item in the returned list:
```json
{
  "metric": "kernel.all.load",
  "instance": "1 minute",
  "score": 3.45,
  "severity": "high",
  "direction": "up",
  "magnitude": 2.1,
  "summary": "Load average 1-min is 3.5σ above baseline mean (0.8 → 2.9)"
}
```

The `summary` field is a pre-computed human-readable sentence derived from the anomaly data — agents can use it directly or reason over the structured fields.

### D5: Error Handling — Fail Fast

All errors from underlying tools propagate via `_mcp_error()`:
- `PmproxyConnectionError` → "Connection error: ... Suggestion: Check pmproxy health"
- `PmproxyTimeoutError` → "Timeout error: ... Suggestion: Check pmproxy responsiveness"
- Discovery returns no metrics → "No metrics found for the specified scope"
- Future timestamp → "Validation error: time_of_interest must be in the past"

No fallback to alternative tools. No partial results.

### D6: Tool Description Updates

Existing tools get description prefixes/suffixes to guide agent behaviour:

- **`pcp_detect_anomalies`**: Add "Use this for targeted anomaly analysis on specific metrics you've already identified. For open-ended investigation, start with `pcp_quick_investigate`."
- **`pcp_compare_windows`**: Add "Use this to compare specific metrics across two known time windows. For open-ended investigation, start with `pcp_quick_investigate`."
- **`pcp_scan_changes`**: Add "Use this to scan for broad changes in a metric prefix. For open-ended investigation, start with `pcp_quick_investigate`."
- **`pcp_fetch_timeseries`**: Add "Use this for targeted retrieval of a specific metric you've already identified. NOT for exploratory investigation — use `pcp_quick_investigate` for discovery."

### D7: Prompt Update

The `investigate_subsystem` prompt in `prompts/investigate.py` will be updated to include explicit tool-ordering guidance:

```
Investigation workflow:
1. Start with pcp_quick_investigate(time_of_interest=...) for broad discovery
2. Use pcp_detect_anomalies or pcp_compare_windows to confirm specific findings
3. Use pcp_fetch_timeseries only for targeted data retrieval of identified metrics
```

## Post-Design Constitution Re-Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Code Quality | PASS | Single-responsibility orchestrator; composes existing functions; no complexity violations |
| II. Testing Standards | PASS | TDD cycle: unit tests mock discovery + anomaly _impl returns; contract test for registration |
| III. UX Consistency | PASS | Error messages follow `_mcp_error()` pattern; clear validation messages for edge cases |
| IV. Performance | PASS | Two sequential calls (discover + detect) — same as existing patterns; 50-result cap prevents bloat |
| V. Simplicity | PASS | ~50 lines of orchestration logic; no new abstractions, patterns, or layers |
