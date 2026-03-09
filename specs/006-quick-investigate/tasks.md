# Tasks: Low-Friction Open-Ended Investigation Entry Point

**Input**: Design documents from `/specs/006-quick-investigate/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/pcp-quick-investigate.md

**Tests**: Per the project constitution (Principle II — Testing Standards, NON-NEGOTIABLE), tests
are mandatory. Unit coverage MUST reach >= 80% and contract tests MUST accompany any interface
change. Test tasks are included below and MUST be written first (Red-Green-Refactor).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: Register the new module so subsequent tasks can import from it

- [X] T001 Add `investigate` import to `src/pmmcp/tools/__init__.py`

---

## Phase 2: User Story 1 — Quick investigate with just a time of interest (Priority: P1) MVP

**Goal**: An operator provides only a `time_of_interest` and receives a ranked anomaly summary. The tool discovers metrics via `_discover_metrics_impl`, computes smart default windows, runs `_detect_anomalies_impl`, and returns structured JSON capped at 50 results.

**Independent Test**: Call `_quick_investigate_impl` with only `time_of_interest` and a mocked client; verify ranked anomaly list is returned with correct structure.

### Tests for User Story 1 *(required per Principle II)*

> **Write these tests FIRST, ensure they FAIL before implementation (Red-Green-Refactor)**

- [X] T002 [P] [US1] Unit test: basic invocation returns ranked anomaly list in `tests/unit/test_investigate.py` — mock `_discover_metrics_impl` to return metric names, mock `_detect_anomalies_impl` to return anomaly data, verify `InvestigationResult` structure (anomalies, metadata, message, truncated)
- [X] T003 [P] [US1] Unit test: time window computation in `tests/unit/test_investigate.py` — verify recent window is centred on `time_of_interest` and baseline ends where recent begins, with defaults of 2 hours lookback and 7 days baseline
- [X] T004 [P] [US1] Unit test: empty anomalies returns "No anomalies detected" message in `tests/unit/test_investigate.py`
- [X] T005 [P] [US1] Unit test: future `time_of_interest` raises validation error in `tests/unit/test_investigate.py`
- [X] T006 [P] [US1] Unit test: results capped at 50, sorted by score descending, `truncated=true` when exceeding cap in `tests/unit/test_investigate.py`
- [X] T007 [P] [US1] Unit test: discovery returns no metrics triggers clear error via `_mcp_error()` in `tests/unit/test_investigate.py`
- [X] T008 [P] [US1] Contract test: `pcp_quick_investigate` is registered and discoverable via `mcp.list_tools()` in `tests/contract/test_mcp_schemas.py`

### Implementation for User Story 1

- [X] T009 [US1] Implement `_quick_investigate_impl` and `pcp_quick_investigate` tool in `src/pmmcp/tools/investigate.py` — orchestrate `_discover_metrics_impl` + `_detect_anomalies_impl` with time window computation, 50-result cap, severity classification, and `_mcp_error()` error handling. Only `time_of_interest` required; hardcode defaults for `lookback="2hours"`, `baseline_days=7`, `subsystem=""`, `host=""`

**Checkpoint**: US1 complete — tool callable with just `time_of_interest`, returns ranked anomaly summary

---

## Phase 3: User Story 2 — Agent naturally reaches for summary tools (Priority: P2)

**Goal**: Tool descriptions and prompt guidance steer agents to use summary/investigation tools before raw `pcp_fetch_timeseries`. The new tool's description signals it as the discovery entry point; existing tools clarify their confirmation/targeted roles.

**Independent Test**: Read tool descriptions and verify steering language is present; read `investigate_subsystem` prompt and verify tool-ordering workflow.

### Tests for User Story 2 *(required per Principle II)*

- [X] T010 [P] [US2] Contract test: `pcp_quick_investigate` description contains "Start here for open-ended investigation" in `tests/contract/test_mcp_schemas.py`
- [X] T011 [P] [US2] Contract test: `pcp_detect_anomalies` description contains steering toward `pcp_quick_investigate` for discovery in `tests/contract/test_mcp_schemas.py`
- [X] T012 [P] [US2] Contract test: `pcp_compare_windows` description contains steering toward `pcp_quick_investigate` for discovery in `tests/contract/test_mcp_schemas.py`
- [X] T013 [P] [US2] Contract test: `pcp_scan_changes` description contains steering toward `pcp_quick_investigate` for discovery in `tests/contract/test_mcp_schemas.py`
- [X] T014 [P] [US2] Contract test: `pcp_fetch_timeseries` description contains "NOT for exploratory investigation" in `tests/contract/test_mcp_schemas.py`
- [X] T015 [P] [US2] Contract/unit test: `investigate_subsystem` prompt includes tool-ordering workflow (quick_investigate -> detect/compare -> fetch) in `tests/contract/test_prompts.py`

### Implementation for User Story 2

- [X] T016 [P] [US2] Update `pcp_detect_anomalies` tool description in `src/pmmcp/tools/anomaly.py` — append steering language per contracts/pcp-quick-investigate.md
- [X] T017 [P] [US2] Update `pcp_compare_windows` tool description in `src/pmmcp/tools/comparison.py` — append steering language
- [X] T018 [P] [US2] Update `pcp_scan_changes` tool description in `src/pmmcp/tools/scanning.py` — append steering language
- [X] T019 [P] [US2] Update `pcp_fetch_timeseries` tool description in `src/pmmcp/tools/timeseries.py` — append "NOT for exploratory investigation" steering
- [X] T020 [US2] Update `investigate_subsystem` prompt in `src/pmmcp/prompts/investigate.py` — add tool-ordering workflow section per D7 in plan.md

**Checkpoint**: US2 complete — all tool descriptions steer agents correctly, prompt includes workflow guidance

---

## Phase 4: User Story 3 — Customise investigation scope (Priority: P3)

**Goal**: Power users can pass optional `subsystem`, `lookback`, and `baseline_days` parameters to narrow or widen investigation scope while keeping smart defaults.

**Independent Test**: Call `_quick_investigate_impl` with optional parameters and verify scoped discovery and custom time windows.

### Tests for User Story 3 *(required per Principle II)*

- [X] T021 [P] [US3] Unit test: `subsystem="disk"` scopes discovery to disk prefix in `tests/unit/test_investigate.py`
- [X] T022 [P] [US3] Unit test: custom `lookback="30minutes"` adjusts recent window width in `tests/unit/test_investigate.py`
- [X] T023 [P] [US3] Unit test: custom `baseline_days=14` extends baseline window in `tests/unit/test_investigate.py`
- [X] T024 [P] [US3] Unit test: `host` parameter is passed through to discovery and anomaly detection in `tests/unit/test_investigate.py`

### Implementation for User Story 3

- [X] T025 [US3] Wire optional parameters (`subsystem`, `lookback`, `baseline_days`, `host`) through `_quick_investigate_impl` in `src/pmmcp/tools/investigate.py` — subsystem filters discovery prefix, lookback/baseline_days adjust window computation, host passes through to client calls

**Checkpoint**: US3 complete — optional parameters scope investigation without breaking defaults

---

## Phase 5: Polish & Cross-Cutting Concerns

- [X] T026 Run `scripts/pre-push-sanity.sh` — lint, format, full test suite with >= 80% coverage
- [X] T027 Run `specs/006-quick-investigate/quickstart.md` verification steps end-to-end

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **US1 (Phase 2)**: Depends on Phase 1 (module registration)
- **US2 (Phase 3)**: Depends on Phase 2 (tool must exist for description tests)
- **US3 (Phase 4)**: Depends on Phase 2 (extends core implementation)
- **Polish (Phase 5)**: Depends on all prior phases

### User Story Dependencies

- **US1 (P1)**: Independent — core tool with defaults only
- **US2 (P2)**: Depends on US1 being registered (description tests reference the tool)
- **US3 (P3)**: Depends on US1 (extends the implementation with optional params)

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Commit test code, then commit implementation code
- Run `scripts/pre-push-sanity.sh` before pushing

### Parallel Opportunities

- **US1 tests** (T002-T008): All parallelizable — different test functions, same file
- **US2 tests** (T010-T015): All parallelizable — different test functions
- **US2 implementation** (T016-T019): All parallelizable — different source files
- **US3 tests** (T021-T024): All parallelizable — different test functions

---

## Parallel Example: User Story 1

```bash
# Launch all US1 tests in parallel (they all target tests/unit/test_investigate.py):
T002: Unit test — basic invocation returns ranked anomaly list
T003: Unit test — time window computation
T004: Unit test — empty anomalies
T005: Unit test — future timestamp validation
T006: Unit test — 50-result cap + sorting
T007: Unit test — no metrics error
T008: Contract test — tool registration
```

## Parallel Example: User Story 2

```bash
# Launch all US2 description updates in parallel (different files):
T016: Update anomaly.py description
T017: Update comparison.py description
T018: Update scanning.py description
T019: Update timeseries.py description
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001)
2. Complete Phase 2: US1 tests (T002-T008) -> RED -> implementation (T009) -> GREEN
3. **STOP and VALIDATE**: `_quick_investigate_impl` works with just `time_of_interest`
4. Push and verify CI

### Incremental Delivery

1. US1 -> Core tool working with defaults (MVP!)
2. US2 -> Agent steering via descriptions + prompt
3. US3 -> Power-user customisation
4. Polish -> Final sanity check

---

## Summary

| Metric | Value |
|--------|-------|
| Total tasks | 27 |
| US1 tasks | 8 (7 test + 1 impl) |
| US2 tasks | 11 (6 test + 5 impl) |
| US3 tasks | 5 (4 test + 1 impl) |
| Setup tasks | 1 |
| Polish tasks | 2 |
| Parallel opportunities | 4 groups (US1 tests, US2 tests, US2 impl, US3 tests) |
| Suggested MVP | US1 only (Phase 1 + Phase 2) |
