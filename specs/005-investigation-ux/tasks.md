# Tasks: Investigation UX Improvements

**Input**: Design documents from `/specs/005-investigation-ux/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/prompt-contracts.md ✓

**Tests**: Mandatory per project constitution (Principle II — Testing Standards). TDD cycle
required — write failing tests, commit, then implement. Coverage gate: ≥80%.

**Organization**: Tasks grouped by user story. US3 (P3) and US4 (P4) are merged into a single
story phase per plan.md — both are pure docstring updates and share one test file.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: Environment verification — no structural changes; existing project layout used as-is.

- [X] T001 Sync dev environment and verify baseline: `uv sync --extra dev && uv run pytest --cov=pmmcp --cov-fail-under=80`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: N/A — all three user stories are fully independent and touch different files.
No shared infrastructure needed. Stories may proceed directly from Phase 1.

---

## Phase 3: User Story 1 — session_init Prompt (Priority: P1) 🎯 MVP

**Goal**: New `session_init` MCP prompt registers `derived.cpu.utilisation`,
`derived.disk.utilisation`, and `derived.mem.utilisation` via `pcp_derive_metric`, verifies
each via `pcp_fetch_live`, and reports success/failure without aborting.

**Independent Test**: Invoke session_init and verify all three metric names appear in content,
`pcp_derive_metric` and `pcp_fetch_live` are referenced, failure handling without abort is
described, and host is interpolated when provided. Contract: prompt listed and resolvable via
`srv.mcp._prompt_manager`.

### Tests for User Story 1 — Write First (TDD)

> **Write tests, run `uv run pytest tests/unit/test_prompts_session_init.py` — MUST FAIL before implementing**

- [X] T002 [US1] Write 9 failing unit tests in tests/unit/test_prompts_session_init.py: test_returns_at_least_one_message, test_messages_have_role_and_content, test_all_three_derived_metric_names_present, test_pcp_derive_metric_referenced_in_content, test_pcp_fetch_live_verification_referenced, test_failure_handling_without_abort_mentioned, test_host_interpolated_when_provided, test_no_none_string_when_host_omitted, test_all_three_expressions_present
- [X] T003 [US1] Add session_init contract assertions (list_prompts includes session_init; get_prompt resolves without error) to tests/contract/test_prompts.py

### Implementation for User Story 1

- [X] T004 [US1] Implement `_session_init_impl(host, timerange) -> list[dict]` pure function with all three metric definitions, pcp_derive_metric calls, pcp_fetch_live verification, and report-without-abort instruction in src/pmmcp/prompts/session_init.py
- [X] T005 [US1] Add `@mcp.prompt() def session_init(host, timerange)` wrapper calling `_session_init_impl` in src/pmmcp/prompts/session_init.py
- [X] T006 [US1] Register session_init via side-effect import in src/pmmcp/prompts/__init__.py

**Checkpoint**: `uv run pytest tests/unit/test_prompts_session_init.py tests/contract/test_prompts.py -v` → all green. Run `/pre-push-sanity` before committing.

---

## Phase 4: User Story 2 — incident_triage 4-Step Sequence (Priority: P2)

**Goal**: Full rewrite of `incident_triage` prompt prescribing an unambiguous four-step
sequence: (1) `pcp_detect_anomalies` → (2) `pcp_compare_windows` → (3) `pcp_scan_changes` →
(4) `pcp_fetch_timeseries`. All existing passing tests remain green.

**Independent Test**: Invoke `incident_triage` and confirm all four steps are named with correct
tools in correct order, transitions use qualitative language (not numeric thresholds), and all
previously-passing assertions hold (symptom/host/timerange interpolation, guard clauses,
subsystem mapping table, fleet scope check, unmappable-symptom fallback).

### Tests for User Story 2 — Write First (TDD)

> **Add to existing test file. New tests MUST FAIL; all existing tests MUST remain GREEN.**

- [X] T007 [US2] Add 6 failing tests to tests/unit/test_prompts_triage.py: test_four_step_sequence_present, test_anomaly_detection_is_first_step, test_window_comparison_is_second_step, test_scan_changes_is_third_step, test_targeted_drilldown_is_fourth_step, test_step_transitions_use_qualitative_language — confirm all existing tests still pass

### Implementation for User Story 2

- [X] T008 [US2] Rewrite `_incident_triage_impl()` in src/pmmcp/prompts/triage.py: replace old Steps 3–4 content with explicit 4-step spine; preserve symptom/host/timerange interpolation, guard clauses (missing-tool abort, out-of-retention stop), symptom-to-subsystem mapping table, fleet-vs-host scope check, and unmappable-symptom fallback

**Checkpoint**: `uv run pytest tests/unit/test_prompts_triage.py -v` → all green (6 new + all existing). Run `/pre-push-sanity` before committing.

---

## Phase 5: User Story 3+4 — Tool Description UX (Priority: P3+P4)

**Goal**: In-place docstring updates for 7 tools. `pcp_detect_anomalies` gets "start here" /
"first tool" language. `pcp_fetch_timeseries` gets "drill-down / after anomalies identified"
language. All six tools with user-supplied `limit` or `max_metrics` get exploration vs analysis
guidance with concrete value of 50. No signature or schema changes.

**Independent Test**: Read updated docstrings and verify: "first" investigation language in
anomaly.py; "drill-down" + "after anomalies" in timeseries.py; concrete value 50 and
when-to-increase guidance in each of the six limit-bearing tools.

### Tests for User Story 3+4 — Write First (TDD)

> **Write tests, run `uv run pytest tests/unit/test_tool_descriptions_ux.py` — MUST FAIL before implementing**

- [X] T009 [US3] Write 8 failing tests in tests/unit/test_tool_descriptions_ux.py: test_detect_anomalies_description_states_use_first, test_fetch_timeseries_description_states_drilldown, test_fetch_timeseries_limit_guidance_present, test_query_series_limit_guidance_present, test_discover_metrics_limit_guidance_present, test_get_hosts_limit_guidance_present, test_search_limit_guidance_present, test_scan_changes_max_metrics_guidance_present

### Implementation for User Story 3+4

- [X] T010 [P] [US3] Update `pcp_detect_anomalies` docstring: add "Start here. Recommended first tool at the start of any investigation" language in src/pmmcp/tools/anomaly.py
- [X] T011 [P] [US3] Update `pcp_fetch_timeseries` docstring: add "drill-down after anomalies are identified" + exploration limit guidance (50); update `pcp_query_series` docstring: add exploration limit guidance (50) in src/pmmcp/tools/timeseries.py
- [X] T012 [P] [US3] Update `pcp_discover_metrics` docstring: add exploration limit guidance (50, increase to 200+ for analysis) in src/pmmcp/tools/discovery.py
- [X] T013 [P] [US3] Update `pcp_get_hosts` docstring: add exploration limit guidance (50) in src/pmmcp/tools/hosts.py
- [X] T014 [P] [US3] Update `pcp_search` docstring: add exploration limit guidance (50, increase to 100+ for full corpus) in src/pmmcp/tools/search.py
- [X] T015 [P] [US3] Update `pcp_scan_changes` `max_metrics` docstring: add guidance (exploration: 50, full scan: increase to 200+) in src/pmmcp/tools/scanning.py

**Checkpoint**: `uv run pytest tests/unit/test_tool_descriptions_ux.py -v` → all green. Run `/pre-push-sanity` before committing.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final end-to-end validation across all stories.

- [X] T016 Run full test suite with coverage gate across all new and modified modules: `uv run pytest --cov=pmmcp --cov-fail-under=80 --cov-report=term-missing`
- [X] T017 [P] Verify ruff lint and format pass across all changed files: `uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: N/A — skipped
- **User Stories (Phase 3–5)**: All independent; can start after T001 — no cross-story dependencies
- **Polish (Phase 6)**: Depends on all desired stories being complete

### User Story Dependencies

- **US1 (P1)**: Independent — start after T001
- **US2 (P2)**: Independent — start after T001 (safe to work concurrently with US1)
- **US3+US4 (P3+P4)**: Independent — start after T001 (safe to work concurrently with US1+US2)

### Within Each User Story (TDD Discipline Required)

1. Write failing tests → confirm RED → `git commit "test: <story>"`
2. Implement → confirm GREEN → `git commit "feat: <story>"`
3. Run `/pre-push-sanity` → `git push`

### Parallel Opportunities

- T002, T007, T009: Test-writing tasks across all stories are fully parallel (different files)
- T010–T015: All six docstring updates touch different files — fully parallelizable after T009
- T016 + T017: Polish tasks are parallel

---

## Parallel Example: User Story 3+4

```bash
# After T009 test commit, all 6 implementation tasks can run concurrently:
Task: T010 — Update anomaly.py docstring
Task: T011 — Update timeseries.py docstrings
Task: T012 — Update discovery.py docstrings
Task: T013 — Update hosts.py docstring
Task: T014 — Update search.py docstring
Task: T015 — Update scanning.py docstring
```

---

## Commit Sequence (per plan.md)

```
test: session_init prompt — pre-register derived metrics          (T002, T003)
feat: session_init prompt — pre-register derived metrics          (T004, T005, T006)
test: incident_triage — explicit 4-step sequence                  (T007)
feat: incident_triage — rewrite with 4-step investigation sequence (T008)
test: tool descriptions — anomaly-first and limit guidance        (T009)
feat: tool descriptions — anomaly-first and limit guidance        (T010–T015)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001)
2. Complete Phase 3: US1 session_init (T002–T006)
3. **STOP and VALIDATE**: All session_init tests green, coverage ≥80%
4. Push — MVP delivered

### Incremental Delivery

1. Setup → US1 → push (MVP)
2. US2 triage rewrite → push
3. US3+US4 tool descriptions → push
4. Each story is independently testable and deployable before the next begins

---

## Notes

- `scanning.py` is named in plan.md; verify it exists at `src/pmmcp/tools/scanning.py` before T015
- `anomaly.py` is named in plan.md for `pcp_detect_anomalies`; verify before T010
- All existing tests in `test_prompts_triage.py` MUST remain green throughout US2 — never delete
- Run `uv sync --extra dev` before any test/lint/build command — fast and idempotent
- [P] tasks = different files, no dependencies — safe to parallelize
