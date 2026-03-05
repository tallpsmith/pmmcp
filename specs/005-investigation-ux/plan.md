# Implementation Plan: Investigation UX Improvements

**Branch**: `005-investigation-ux` | **Date**: 2026-03-04 | **Spec**: `specs/005-investigation-ux/spec.md`
**Input**: Feature specification from `/specs/005-investigation-ux/spec.md`

## Summary

Improve the investigation UX across four dimensions: (1) add a `session_init` prompt that
pre-registers three canonical derived metrics, (2) rewrite `incident_triage` to prescribe
an explicit four-step anomaly → compare → scan → drilldown sequence, (3) update
`pcp_detect_anomalies` to declare itself the first investigation tool and `pcp_fetch_timeseries`
to declare itself a drill-down tool, (4) add exploration vs analysis limit guidance to all
tools with a user-supplied `limit` parameter. All changes are text/docstring changes plus
one new prompt module — no schema changes, no signature changes, no breaking changes.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: `mcp[cli]` ≥1.2.0 (FastMCP), `pydantic` v2.x
**Storage**: N/A — no data storage
**Testing**: `pytest`, `pytest-asyncio`
**Target Platform**: Any (pure Python, runs wherever pmproxy is reachable)
**Project Type**: Single project
**Performance Goals**: N/A — text/description changes; no latency SLAs apply
**Constraints**: Must not break existing passing tests in `test_prompts_triage.py`
**Scale/Scope**: 3 user stories, 1 new module, 6+ docstring updates

## Constitution Check

| Principle | Status | Notes / Justification |
|-----------|--------|----------------------|
| I. Code Quality — linting enforced, single-responsibility, complexity ≤ 10, peer review | **PASS** | ruff enforced in CI; each prompt/tool module has a single responsibility; new `session_init.py` mirrors existing prompt modules; complexity ≤ 5 |
| II. Testing Standards — TDD cycle, ≥ 80% unit coverage, contract tests on interface changes | **PASS** | Story-by-story TDD: failing tests committed before implementation per story; new prompt has full unit test coverage; `session_init` is a new public interface → contract tests added; existing triage tests preserved and extended |
| III. UX Consistency — design system adherence, WCAG 2.1 AA, actionable error messages | **PASS** | These changes ARE the UX improvements; all follow existing tool description and prompt copy patterns; actionable error wording in session_init (report failure, don't abort) |
| IV. Performance — latency SLA defined, performance budget in CI, profiling before optimization | **N/A** | Pure text changes to docstrings and prompt return values; no code paths with latency implications are touched |
| V. Simplicity — YAGNI posture, no speculative abstractions, complexity justified below | **PASS** | Minimum viable changes: one new file, docstring edits, prompt rewrite. No new abstractions. No over-engineering. |

## Project Structure

### Documentation (this feature)

```text
specs/005-investigation-ux/
├── plan.md              # This file
├── research.md          # Phase 0 output — all decisions resolved
├── data-model.md        # Phase 1 output — prompt signatures + tool changes
├── quickstart.md        # Phase 1 output — how to use new features
├── contracts/
│   └── prompt-contracts.md  # Phase 1 output — observable prompt behaviour
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT yet created)
```

### Source Code

```text
src/pmmcp/
├── prompts/
│   ├── __init__.py           # MODIFIED: add session_init import
│   ├── session_init.py       # NEW: session_init prompt
│   └── triage.py             # MODIFIED: full rewrite with 4-step spine
└── tools/
    ├── anomaly.py            # MODIFIED: docstring — "start here" language
    ├── timeseries.py         # MODIFIED: docstrings — drill-down + limit guidance
    ├── discovery.py          # MODIFIED: docstring — limit guidance
    ├── hosts.py              # MODIFIED: docstring — limit guidance
    ├── search.py             # MODIFIED: docstring — limit guidance
    └── scanning.py           # MODIFIED: docstring — max_metrics guidance

tests/unit/
├── test_prompts_session_init.py   # NEW: unit tests for session_init
├── test_prompts_triage.py         # MODIFIED: add 4-step sequence tests (keep all existing)
└── test_tool_descriptions_ux.py   # NEW: unit tests for updated tool descriptions
```

**Structure Decision**: Single project — existing layout, no new layers.

## Complexity Tracking

> No Constitution Check violations — table is empty.

## Implementation Stories

Stories executed in priority order, one at a time, TDD story-by-story loop per Constitution §II.

---

### Story 1 (P1): session_init Prompt — Pre-register Derived Metrics

**Files touched**:
- `tests/unit/test_prompts_session_init.py` (NEW — failing tests first)
- `src/pmmcp/prompts/session_init.py` (NEW)
- `src/pmmcp/prompts/__init__.py` (add import)

**Failing tests to write** (commit `test: session_init prompt — pre-register derived metrics`):

```python
# test_prompts_session_init.py
def test_returns_at_least_one_message()
def test_messages_have_role_and_content()
def test_all_three_derived_metric_names_present()
    # derived.cpu.utilisation, derived.disk.utilisation, derived.mem.utilisation
def test_pcp_derive_metric_referenced_in_content()
def test_pcp_fetch_live_verification_referenced()
def test_failure_handling_without_abort_mentioned()
def test_host_interpolated_when_provided()
def test_no_none_string_when_host_omitted()
def test_all_three_expressions_present()
    # The actual PCP expressions (at least the metric names derived.*)
```

**Implementation** (commit `feat: session_init prompt — pre-register derived metrics`):

`session_init.py` returns a prompt that instructs Claude to:
1. Register each of the three derived metrics via `pcp_derive_metric`
2. Call `pcp_fetch_live` for each to verify availability
3. Report which succeeded/failed without aborting

Pattern: `_session_init_impl(host, timerange) -> list[dict]` + `@mcp.prompt() def session_init()`

---

### Story 2 (P2): incident_triage — Explicit 4-Step Investigation Sequence

**Files touched**:
- `tests/unit/test_prompts_triage.py` (MODIFIED — add new tests, keep all existing)
- `src/pmmcp/prompts/triage.py` (MODIFIED — full rewrite)

**Failing tests to write** (commit `test: incident_triage — explicit 4-step sequence`):

```python
# Added to test_prompts_triage.py (existing tests MUST continue to pass)
def test_four_step_sequence_present()
    # All four step names present in the content
def test_anomaly_detection_is_first_step()
    # pcp_detect_anomalies named as Step 1
def test_window_comparison_is_second_step()
    # pcp_compare_windows named as Step 2
def test_scan_changes_is_third_step()
    # pcp_scan_changes named as Step 3
def test_targeted_drilldown_is_fourth_step()
    # pcp_fetch_timeseries named as Step 4
def test_step_transitions_use_qualitative_language()
    # Transition criteria are qualitative ("if anomalies found") not numeric thresholds
```

**Implementation** (commit `feat: incident_triage — rewrite with 4-step investigation sequence`):

Full rewrite of `triage.py` content. The four-step spine becomes the primary structure.
Existing passing tests constrain what must be preserved:
- Symptom/host/timerange interpolation
- Guard clauses (missing tool, out-of-retention)
- Symptom-to-subsystem mapping table
- Fleet-wide scope confirmation

---

### Story 3 (P3+P4): Tool Description UX — anomaly-first + limit guidance

**Files touched**:
- `tests/unit/test_tool_descriptions_ux.py` (NEW — failing tests first)
- `src/pmmcp/tools/anomaly.py` (docstring update)
- `src/pmmcp/tools/timeseries.py` (docstring updates × 2)
- `src/pmmcp/tools/discovery.py` (docstring update)
- `src/pmmcp/tools/hosts.py` (docstring update)
- `src/pmmcp/tools/search.py` (docstring update)
- `src/pmmcp/tools/scanning.py` (docstring update)

**Failing tests to write** (commit `test: tool descriptions — anomaly-first and limit guidance`):

```python
# test_tool_descriptions_ux.py
def test_detect_anomalies_description_states_use_first()
    # Docstring contains "first" investigation language
def test_fetch_timeseries_description_states_drilldown()
    # Docstring contains "drill-down" / "after anomalies" language
def test_fetch_timeseries_limit_guidance_present()
    # Docstring mentions "50" as exploration default and guidance to increase
def test_query_series_limit_guidance_present()
def test_discover_metrics_limit_guidance_present()
def test_get_hosts_limit_guidance_present()
def test_search_limit_guidance_present()
def test_scan_changes_max_metrics_guidance_present()
```

**Implementation** (commit `feat: tool descriptions — anomaly-first and limit guidance`):

In-place docstring edits. No signature changes. No schema changes.

For each `limit`-bearing tool, add to the `limit` arg description:
> "For exploration use 50; increase for full dataset analysis."

---

## Pre-Push Checklist (per story)

After each story's implementation commit, before `git push`:

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run pytest --cov=pmmcp --cov-fail-under=80
```

Or invoke `/pre-push-sanity`.

## Commit Sequence

```
test: session_init prompt — pre-register derived metrics
feat: session_init prompt — pre-register derived metrics
test: incident_triage — explicit 4-step sequence
feat: incident_triage — rewrite with 4-step investigation sequence
test: tool descriptions — anomaly-first and limit guidance
feat: tool descriptions — anomaly-first and limit guidance
```
