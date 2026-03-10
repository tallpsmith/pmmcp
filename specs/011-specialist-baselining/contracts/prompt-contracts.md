# Prompt Contracts: Specialist Historical Baselining

**Feature**: 011-specialist-baselining | **Date**: 2026-03-10

## Contract: No Interface Changes

This feature makes **zero changes** to function signatures or MCP protocol surface.

### specialist_investigate (UNCHANGED)

```python
def specialist_investigate(
    subsystem: str,
    request: str | None = None,
    host: str | None = None,
    time_of_interest: str | None = None,
    lookback: str | None = None,
) -> list[dict]:
```

- Parameters: unchanged
- Return type: `list[dict]` — unchanged
- MCP registration: unchanged

### coordinate_investigation (UNCHANGED)

```python
def coordinate_investigation(
    request: str,
    host: str | None = None,
    time_of_interest: str | None = None,
    lookback: str | None = None,
) -> list[dict]:
```

- Parameters: unchanged
- Return type: `list[dict]` — unchanged
- MCP registration: unchanged

## Content Contracts (Unit Test Assertions)

Since no interfaces change, the "contracts" for this feature are content assertions verified in unit tests:

| Contract | Verified By |
|----------|------------|
| Domain specialists (5) include Baseline step | String assertion: "Baseline" in workflow for cpu, memory, disk, network, process |
| Cross-cutting does NOT include Baseline step | String assertion: "Baseline" NOT in cross-cutting workflow |
| Classification fields in report guidance | String assertion: "classification", "ANOMALY", "RECURRING", "BASELINE" |
| `baseline_context` in report guidance | String assertion: "baseline_context" |
| `severity_despite_baseline` in report guidance | String assertion: "severity_despite_baseline" |
| Coordinator ranks by classification | String assertion: "ANOMALY" ranking guidance in synthesis |
| Graceful degradation | String assertion: "insufficient baseline" or fallback in prompt |

## Existing Contract Tests (UNCHANGED)

The existing contract tests in `tests/contract/test_prompts.py` continue to pass unchanged — they verify prompt registration and argument schemas, which are not modified.
