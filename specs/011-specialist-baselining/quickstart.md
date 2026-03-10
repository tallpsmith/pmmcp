# Quickstart: Specialist Historical Baselining

**Feature**: 011-specialist-baselining | **Date**: 2026-03-10

## What Changed

Domain specialist prompts now include a **Baseline step** that instructs the investigating agent to fetch 7-day historical data and classify each finding as ANOMALY, RECURRING, or BASELINE. The coordinator ranks anomalies above baseline behaviour in its synthesis.

## Verify It Works

```bash
# Run all tests (baseline assertions included)
uv run pytest tests/unit/test_prompts_specialist.py tests/unit/test_prompts_coordinator.py -v

# Full suite with coverage
uv run pytest --cov=pmmcp --cov-report=term-missing
```

## Key Files

| File | Change |
|------|--------|
| `src/pmmcp/prompts/specialist.py` | Baseline step, classification fields, baseline-aware heuristics, graceful degradation |
| `src/pmmcp/prompts/coordinator.py` | Classification-based ranking in synthesis phase |
| `docs/investigation-flow.md` | 5-step workflow diagram |
| `tests/unit/test_prompts_specialist.py` | Baseline/classification presence assertions |
| `tests/unit/test_prompts_coordinator.py` | Classification ranking assertions |

## How Classification Works

The specialist prompt instructs the agent to:
1. **Baseline step**: Fetch 7-day history at 1hour interval, run `pcp_detect_anomalies`
2. **Classify each finding**:
   - **ANOMALY**: Significant deviation from baseline, not a recurring pattern
   - **RECURRING**: Spikes that repeat at the same time of day (batch jobs, backups)
   - **BASELINE**: Normal behaviour for this host
3. **Severity despite baseline**: A finding can be BASELINE and still critical (chronic degradation)

## Impact on Existing Prompts

- **No signature changes** — `specialist_investigate` and `coordinate_investigation` accept the same parameters
- **No tool changes** — `pcp_detect_anomalies`, `pcp_quick_investigate`, etc. are unchanged
- **No new dependencies** — pure prompt text additions
- **Cross-cutting specialist** does NOT get a Baseline step — it consumes classifications from domain specialists
