# Prompt Contracts: Investigation UX Improvements

**Feature**: 005-investigation-ux

These contracts define the observable behaviour of MCP prompts in this feature.
They drive the contract test tier (`tests/contract/`).

---

## Contract: `session_init` Prompt

**New prompt** — full contract.

### Input Schema

```
session_init(
  host?:      string | null   # target host; null = all hosts
  timerange?: string | null   # pmproxy relative time; null = default
)
```

### Output Contract

- Returns `list[PromptMessage]` with ≥1 message
- Each message has `role == "user"` and non-empty `content`
- Content contains all three derived metric names:
  - `derived.cpu.utilisation`
  - `derived.disk.utilisation`
  - `derived.mem.utilisation`
- Content references `pcp_derive_metric` (the registration tool)
- Content references `pcp_fetch_live` (the verification step)
- Content describes the action to take on failure (report without aborting)

### Registration in MCP

- Prompt is listed by `mcp._prompt_manager.list_prompts()` after import
- `mcp.get_prompt("session_init")` resolves without error

---

## Contract: `incident_triage` Prompt (modified)

**Existing prompt** — modified contract. Must not break existing passing tests.

### Input Schema (unchanged)

```
incident_triage(
  symptom:    string           # required
  host?:      string | null
  timerange?: string | null
)
```

### Output Contract (new requirements)

In addition to all existing contract assertions:

- Content names all four investigation steps in sequence
- Content references `pcp_detect_anomalies` as Step 1
- Content references `pcp_compare_windows` as Step 2
- Content references `pcp_scan_changes` as Step 3
- Content references `pcp_fetch_timeseries` as Step 4 (targeted drilldown only)
- Step transition criteria use qualitative language (no hardcoded z-score numbers)

### Existing contract (must continue to pass)

- Symptom is interpolated into content
- Host is interpolated when provided
- "None" does not appear when host is omitted
- Timerange is interpolated when provided
- Symptom-to-subsystem mapping guidance present (≥3 subsystems named)
- Fleet-wide vs host-specific scope check present
- Missing-tool abort guard present
- Out-of-retention stop guard present
- Unmappable symptom fallback to general sweep mentioned

---

## Contract: Tool Description Updates

These are validated via unit tests that read docstrings directly.

### `pcp_detect_anomalies`

- Docstring includes "first" investigation language (e.g., "start here", "first tool")

### `pcp_fetch_timeseries`

- Docstring includes "drill-down" language
- Docstring indicates it is for use after anomalies are identified

### All `limit`-accepting tools

Each tool's docstring includes:
- A concrete exploration value (50)
- Guidance on when to increase beyond exploration default
