# Implementation Plan: Specialist Historical Baselining

**Branch**: `011-specialist-baselining` | **Date**: 2026-03-10 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/011-specialist-baselining/spec.md`

## Summary

Add 7-day historical baselining to domain specialist prompts so each finding is classified as ANOMALY, RECURRING, or BASELINE. This eliminates false alarms on known patterns (daily batch jobs, normal working-set growth) by inserting a Baseline step between Discover and Fetch in each specialist's workflow. The coordinator synthesis phase ranks anomalies above baseline/recurring findings. This is purely prompt engineering — no new tools, no new dependencies, no API changes.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: `mcp[cli]` ≥1.2.0 (FastMCP), `pydantic` v2.x — no new dependencies
**Storage**: N/A — prompts are stateless text generators
**Testing**: pytest + pytest-asyncio, unit tests asserting prompt output content
**Target Platform**: MCP server (stdio JSON-RPC)
**Project Type**: Single project
**Performance Goals**: N/A — prompt rendering is synchronous string interpolation
**Constraints**: No changes to tool signatures or MCP protocol surface
**Scale/Scope**: 3 files modified (specialist.py, coordinator.py, investigation-flow.md), ~200 lines of prompt text added

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes / Justification |
|-----------|--------|----------------------|
| I. Code Quality — linting enforced, single-responsibility, complexity ≤ 10, peer review, documentation impact reviewed | PASS | Pure text additions to existing prompt modules. No new functions, no complexity increase. Ruff enforced. Docs impact: `docs/investigation-flow.md` (workflow diagram update), `README.md` prompt table (no signature changes, but specialist workflow description needs update). |
| II. Testing Standards — TDD cycle, ≥ 80% unit coverage, contract tests on interface changes | PASS | TDD: write tests asserting baseline/classification presence → implement prompt changes → green. No interface changes (same function signatures). Coverage ≥80% maintained. |
| III. UX Consistency — design system adherence, WCAG 2.1 AA, actionable error messages | N/A | No user-facing UI. Prompt text follows existing specialist output patterns. |
| IV. Performance — latency SLA defined, performance budget in CI, profiling before optimization | N/A | No runtime performance impact — prompt rendering is string interpolation. The additional 7-day fetch is an LLM-executed action, not our code. |
| V. Simplicity — YAGNI posture, no speculative abstractions, complexity justified below | PASS | No new abstractions. Classification is LLM judgement guided by prompt text. No new tools, no periodicity detection, no configuration — YAGNI respected. |

## Project Structure

### Documentation (this feature)

```text
specs/011-specialist-baselining/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (report structure)
├── quickstart.md        # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (files modified)

```text
src/pmmcp/prompts/
├── specialist.py        # Add Baseline step, classification, domain heuristics
└── coordinator.py       # Add classification-based ranking in synthesis

docs/
└── investigation-flow.md  # Update workflow diagram to 5-step flow

tests/unit/
├── test_prompts_specialist.py  # New assertions for baseline/classification
└── test_prompts_coordinator.py # New assertions for classification ranking
```

**Structure Decision**: Existing single-project layout. All changes are modifications to existing files — no new modules created.

## Complexity Tracking

> No violations. All changes are additive text within existing modules.

---

## Design: Changes by File

### 1. `src/pmmcp/prompts/specialist.py`

#### 1a. Workflow: Insert Baseline Step (Step 2)

Current 4-step workflow becomes 5 steps: **Discover → Baseline → Fetch → Analyse → Report**

The Baseline step (for all 5 domain specialists, NOT cross-cutting) instructs the agent to:

1. Fetch 7-day historical data at 1hour interval using `pcp_fetch_timeseries` for the discovered metrics
2. Run `pcp_detect_anomalies` comparing the investigation window against the 7-day baseline
3. Note anomaly detection results for use in the Analyse step
4. If `pcp_detect_anomalies` returns insufficient data or errors, note the limitation and proceed with threshold-only analysis

#### 1b. Report Structure: Add Classification Fields

Each finding in the specialist report gains three new fields:

- `classification`: ANOMALY | RECURRING | BASELINE
- `baseline_context`: human-readable comparison (e.g., "CPU idle has been below 15% for the past 7 days")
- `severity_despite_baseline`: threshold-based severity independent of classification (critical/warning/info/none)

Report guidance instructs the agent to:
- Articulate chronic problems narratively ("this is bad, but based on previous days this is not a new problem")
- Distinguish RECURRING from BASELINE by examining timeseries shape for time-of-day correlation

#### 1c. Domain Knowledge: Add Baseline-Aware Heuristics

Each subsystem gets at least one baseline-aware heuristic:

- **CPU**: Check whether current CPU levels are typical for this time of day over the past week before flagging saturation
- **Memory**: Compare memory growth against 7-day baseline to distinguish leaks from normal working-set growth
- **Disk**: Check whether I/O spikes recur at the same time daily (scheduled jobs like backups, log rotation)
- **Network**: Check whether current packet drop rate is within normal variance for this interface over the past week
- **Process**: Check whether process count and context switch rate match the 7-day pattern before flagging runaway processes

#### 1d. Cross-Cutting: Classification Consumption (No Baseline Step)

Cross-cutting domain knowledge updated to:
- Prioritise ANOMALY-classified findings over RECURRING or BASELINE
- Flag correlated anomalies across multiple subsystems at the same timestamp
- Note when one subsystem reports BASELINE while another reports ANOMALY (the anomaly is more likely root cause)

#### 1e. Graceful Degradation

The Baseline step includes fallback instructions:
- If `pcp_detect_anomalies` returns insufficient data: fall back to threshold-only analysis
- Note "insufficient baseline data, falling back to threshold-only analysis" in the report
- If baseline data exists but is sparse: attempt anomaly detection but note reduced confidence
- If 0 days of history: skip Baseline step entirely, proceed with threshold-only Fetch → Analyse → Report

### 2. `src/pmmcp/prompts/coordinator.py`

#### 2a. Synthesis Phase: Classification-Based Ranking

Update the synthesis section to:
- Always rank ANOMALY findings above BASELINE/RECURRING regardless of severity
- Within each classification tier, sort by severity (critical → warning → info)
- Explicitly call out findings that are normal behaviour for the host
- Highlight when an apparent anomaly matches a known recurring pattern

#### 2b. Output Structure Update

The "Findings by Severity" section becomes "Findings by Classification & Severity":

```
## Findings by Classification & Severity

### New Anomalies (changed from baseline)
1. [CRITICAL] ...
2. [WARNING] ...

### Recurring Patterns (known periodic behaviour)
1. ...

### Baseline Behaviour (chronic conditions)
1. [WARNING] ... (your normal is degraded — here's context)

### Normal Operation
- No anomalies detected for: [subsystems]
```

### 3. `docs/investigation-flow.md`

Update the specialist workflow diagram from 4-step to 5-step:
- Discover → **Baseline** → Fetch → Analyse → Report
- Note that cross-cutting does NOT include the Baseline step
- Update the prompt table if it references specialist workflow steps

## Test Strategy

All tests are unit tests asserting prompt output string content — same pattern as existing tests.

### Specialist Tests (Story 1 + 2 + 5)

| Test | Asserts |
|------|---------|
| Baseline step present for all 5 domain subsystems | "Baseline" in workflow, `pcp_detect_anomalies` referenced |
| Baseline step absent for cross-cutting | "Baseline" NOT in cross-cutting workflow |
| Classification fields in report structure | "classification", "ANOMALY", "RECURRING", "BASELINE" in report guidance |
| `baseline_context` in report structure | "baseline_context" in report guidance |
| `severity_despite_baseline` in report structure | "severity_despite_baseline" in report guidance |
| Domain heuristics reference baseline | Each subsystem has at least one baseline-aware heuristic |
| Graceful degradation instructions present | "insufficient baseline" or fallback guidance in prompt |
| 7-day window referenced | "7-day" or "7 day" in baseline instructions |
| `pcp_fetch_timeseries` referenced in baseline | Tool name appears in baseline step |

### Cross-Cutting Tests (Story 3)

| Test | Asserts |
|------|---------|
| Classification prioritisation in domain knowledge | "ANOMALY" prioritised over "RECURRING"/"BASELINE" |
| Correlated anomaly detection guidance | Cross-subsystem correlation referenced |
| Mixed classification guidance | Guidance for BASELINE + ANOMALY across subsystems |

### Coordinator Tests (Story 4)

| Test | Asserts |
|------|---------|
| Classification ranking in synthesis | "ANOMALY" ranked above "BASELINE"/"RECURRING" |
| Baseline behaviour call-out | Normal behaviour explicitly mentioned |
| Recurring pattern highlighting | Pattern matching guidance present |

## Implementation Order

Stories are independent enough for parallel implementation in worktrees:

**Worktree A**: Stories 1 + 2 + 5 (specialist.py changes + specialist tests)
- These are tightly coupled — baseline step, domain heuristics, and degradation are all in the same `_SPECIALIST_KNOWLEDGE` dict and workflow template

**Worktree B**: Story 3 + 4 (cross-cutting + coordinator changes + tests)
- Cross-cutting domain knowledge update + coordinator synthesis update + their tests

**Final merge**: Story 3+4 depends on Story 1+2 classification fields existing, but since they're prompt text (not runtime dependencies), the tests can assert independently. Merge worktree A first, then worktree B.

**Docs** (investigation-flow.md): Can be done in either worktree or main branch after merge.
