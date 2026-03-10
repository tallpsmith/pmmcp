# Investigation Hierarchy Guardrails

**Date:** 2026-03-10
**Issue:** Partial implementation of #10 (External Integration Contracts)
**Problem:** Claude bypasses the coordinator prompt and calls raw pmmcp tools directly, missing the investigation workflow and Grafana visualisation step.

## Context

The investigation prompt hierarchy is:

```
session_init → coordinate_investigation → specialist_investigate (×6)
```

In practice, Claude skips the entire funnel and calls `pcp_quick_investigate`, `pcp_fetch_timeseries`, etc. directly. This means:

1. No parallel specialist dispatch (slower, less thorough)
2. No structured synthesis with cross-subsystem correlation
3. No Grafana dashboard creation (the "paint a picture" gap)
4. No fallback cascade (Grafana → HTML → text)

## Changes

### A. Tool descriptions — coordinator breadcrumbs

Add a one-liner to tool docstrings that the LLM reads at decision time:

| Tool | Added line |
|------|-----------|
| `pcp_quick_investigate` | "For broad investigations, use the `coordinate_investigation` prompt instead — it dispatches 6 specialists in parallel." |
| `pcp_fetch_timeseries` | "For broad investigations, start with `coordinate_investigation` rather than fetching metrics directly." |
| `pcp_detect_anomalies` | Same pattern |
| `pcp_scan_changes` | Same pattern |

These go at the end of the existing docstring, clearly separated.

### B. `session_init` — assertive coordinator guidance + Grafana preflight

Two additions:

1. **Coordinator guidance** moves from a polite "Next Step" afterthought at the bottom to an **IMPORTANT** block near the top. Language: "ALWAYS use `coordinate_investigation` for broad performance investigations. Do NOT call individual tools or specialist prompts directly unless you have a specific, targeted question about a single metric."

2. **Grafana preflight discovery** (per issue #10):
   - Call `mcp-grafana.list_datasources`
   - Find datasource of type `performancecopilot-*`
   - Validate shared pmproxy URL
   - Cache datasource UID in conversation context
   - Log result (available / unavailable)

### C. Specialist prompt descriptions — hierarchy context

Add to `specialist_investigate` docstring:

> "Typically dispatched by `coordinate_investigation` as part of a parallel 6-specialist sweep. For broad 'something is wrong' investigations, start with the coordinator instead."

### D. `coordinate_investigation` — Phase 3 visualisation

Add Phase 3 after synthesis (per issue #10):

> "After synthesis, if mcp-grafana is available, create a triage dashboard in the configured folder (default `pmmcp-triage`), named `YYYY-MM-DD <summary>`, tagged `pmmcp-generated`, and return the deeplink to the user."

Includes the fallback cascade:
1. Grafana available → dashboard + deeplink
2. Grafana unavailable → offer HTML report to `report_dir`
3. User declines both → text/table output (existing behaviour)

Also includes the auto-trigger heuristic: "If your investigation has surfaced findings across 3+ metrics or 2+ subsystems, and you haven't already created a visualisation, consider offering one."

### E. Config additions

Add to `ServerConfig` (env prefix `PMMCP_`, not `PmproxyConfig` which is for pmproxy connection settings):

| Setting | Env var | Default | Purpose |
|---------|---------|---------|---------|
| `grafana_folder` | `PMMCP_GRAFANA_FOLDER` | `pmmcp-triage` | Grafana folder for generated dashboards |
| `report_dir` | `PMMCP_REPORT_DIR` | `~/.pmmcp/reports/` | Output directory for HTML fallback reports |

## Files Modified

| File | Change |
|------|--------|
| `src/pmmcp/tools/timeseries.py` | Docstring additions to `pcp_fetch_timeseries` |
| `src/pmmcp/tools/discovery.py` | Docstring additions to `pcp_quick_investigate` |
| `src/pmmcp/tools/comparison.py` | Docstring additions to `pcp_detect_anomalies`, `pcp_scan_changes` |
| `src/pmmcp/prompts/session_init.py` | Assertive coordinator guidance + Grafana preflight |
| `src/pmmcp/prompts/specialist.py` | Hierarchy context in docstring |
| `src/pmmcp/prompts/coordinator.py` | Phase 3 visualisation + fallback cascade |
| `src/pmmcp/config.py` | `grafana_folder`, `report_dir` settings |
| `CLAUDE.md` | Document new conventions |

## Files NOT Modified

- No new tools (zero Python tool code beyond config)
- No Grafana JSON templates
- No new dependencies
- Specialist prompt `_SPECIALIST_KNOWLEDGE` content unchanged — only the `@mcp.prompt()` docstring and `specialist_investigate` description change

## Testing Strategy

- Unit tests for new config fields (defaults, env var override)
- Contract tests confirming prompt output includes new guidance text
- Existing tests remain unchanged (no behavioural changes to tools)
- Manual validation: run an investigation session and verify Claude follows the hierarchy
