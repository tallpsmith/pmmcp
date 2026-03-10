# Tasks: Specialist Historical Baselining

**Input**: Design documents from `/specs/011-specialist-baselining/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Per the project constitution (Principle II — Testing Standards, NON-NEGOTIABLE), tests
are mandatory. Unit coverage MUST reach ≥ 80% and contract tests MUST accompany any interface
change. TDD cycle: write failing tests → implement → refactor.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/`, `tests/` at repository root

---

## Phase 1: Setup

**Purpose**: No new dependencies or project structure changes. This feature is purely prompt text modifications to existing files.

- [x] T001 Verify existing tests pass and baseline coverage in `tests/unit/test_prompts_specialist.py` and `tests/unit/test_prompts_coordinator.py` by running `uv run pytest tests/unit/test_prompts_specialist.py tests/unit/test_prompts_coordinator.py --cov=pmmcp.prompts -v`

**Checkpoint**: Green baseline confirmed — all existing prompt tests pass, coverage baseline recorded.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: No foundational/blocking prerequisites for this feature. All changes are additive text to existing prompt modules. User story phases can begin immediately after Phase 1 confirmation.

---

## Phase 3: User Story 1 — Specialist findings include anomaly classification (Priority: P1) MVP

**Goal**: Insert a Baseline step (step 2) into the 5 domain specialist workflows and add classification/baseline_context/severity_despite_baseline fields to the report structure. Cross-cutting does NOT get a Baseline step.

**Independent Test**: Invoke `_specialist_investigate_impl(subsystem="cpu")` and verify the prompt output includes instructions to fetch a 7-day baseline, run `pcp_detect_anomalies`, and classify each finding.

**Worktree**: A (specialist.py changes — shares worktree with US2 and US5)

### Tests for User Story 1 *(required per Principle II — Testing Standards)*

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation (Red-Green-Refactor)**

- [x] T002 [US1] Write test in `tests/unit/test_prompts_specialist.py` asserting that `_specialist_investigate_impl()` output for each of the 5 domain subsystems (cpu, memory, disk, network, process) contains a "Baseline" step between Discover and Fetch that references `pcp_fetch_timeseries` and `pcp_detect_anomalies` and a "7-day" or "7 day" baseline window
- [x] T003 [US1] Write test in `tests/unit/test_prompts_specialist.py` asserting that `_specialist_investigate_impl(subsystem="crosscutting")` output does NOT contain a "Baseline" step (cross-cutting consumes classifications, it doesn't baseline independently)
- [x] T004 [US1] Write test in `tests/unit/test_prompts_specialist.py` asserting that `_specialist_investigate_impl()` output for each of the 5 domain subsystems includes `classification`, `ANOMALY`, `RECURRING`, `BASELINE`, `baseline_context`, and `severity_despite_baseline` in the report structure guidance
- [x] T005 [US1] Write test in `tests/unit/test_prompts_specialist.py` asserting that `_specialist_investigate_impl()` output for domain subsystems includes narrative guidance for chronic problems (e.g., references to "not a new problem" or "your normal" or similar phrasing that instructs the agent to contextualise baseline-classified findings)
- [x] T006 [US1] Run tests and confirm they FAIL (RED): `uv run pytest tests/unit/test_prompts_specialist.py -v -k "baseline or classification"` — commit failing tests

### Implementation for User Story 1

- [x] T007 [US1] In `src/pmmcp/prompts/specialist.py`, add a Baseline step (step 2) to the specialist workflow template for domain subsystems only (cpu, memory, disk, network, process). The step instructs the agent to: (1) fetch 7-day historical data at 1hour interval using `pcp_fetch_timeseries`, (2) run `pcp_detect_anomalies` comparing investigation window against 7-day baseline, (3) note results for the Analyse step. Cross-cutting workflow remains unchanged (4 steps).
- [x] T008 [US1] In `src/pmmcp/prompts/specialist.py`, update the report structure/guidance for domain subsystems to include three new fields: `classification` (ANOMALY/RECURRING/BASELINE), `baseline_context` (human-readable comparison), `severity_despite_baseline` (threshold severity independent of classification). Add narrative guidance for RECURRING detection (time-of-day correlation in 7-day timeseries) and chronic problem articulation.
- [x] T009 [US1] Run tests and confirm they PASS (GREEN): `uv run pytest tests/unit/test_prompts_specialist.py -v` — commit implementation

**Checkpoint**: Domain specialist prompts now include Baseline step and classification fields. Cross-cutting unchanged.

---

## Phase 4: User Story 2 — Domain knowledge augmented with baseline-aware guidance (Priority: P1)

**Goal**: Add at least one baseline-aware heuristic to each domain specialist's domain knowledge section so threshold judgements reference the 7-day baseline before flagging.

**Independent Test**: Read the domain knowledge for each subsystem and verify at least one heuristic references the baseline or `pcp_detect_anomalies`.

**Worktree**: A (same worktree as US1 — same file, same data structure)

### Tests for User Story 2 *(required per Principle II — Testing Standards)*

- [x] T010 [US2] Write test in `tests/unit/test_prompts_specialist.py` asserting that the `_SPECIALIST_KNOWLEDGE` domain_knowledge for CPU contains guidance to check whether current CPU levels are typical for this time of day over the past week before flagging saturation
- [x] T011 [US2] Write test in `tests/unit/test_prompts_specialist.py` asserting that the `_SPECIALIST_KNOWLEDGE` domain_knowledge for Memory contains guidance to compare memory growth against the 7-day baseline to distinguish leaks from normal working-set growth
- [x] T012 [US2] Write test in `tests/unit/test_prompts_specialist.py` asserting that the `_SPECIALIST_KNOWLEDGE` domain_knowledge for Disk contains guidance to check whether I/O spikes recur at the same time daily (scheduled jobs)
- [x] T013 [US2] Write test in `tests/unit/test_prompts_specialist.py` asserting that the `_SPECIALIST_KNOWLEDGE` domain_knowledge for Network and Process each contain at least one baseline-aware heuristic (referencing "baseline" or "7-day" or "past week" or similar)
- [x] T014 [US2] Run tests and confirm they FAIL (RED): `uv run pytest tests/unit/test_prompts_specialist.py -v -k "baseline_heuristic or domain_knowledge_baseline"` — commit failing tests

### Implementation for User Story 2

- [x] T015 [US2] In `src/pmmcp/prompts/specialist.py`, add baseline-aware heuristic to CPU domain_knowledge: check whether current CPU levels are typical for this time of day over the past week before flagging saturation
- [x] T016 [US2] In `src/pmmcp/prompts/specialist.py`, add baseline-aware heuristic to Memory domain_knowledge: compare memory growth against 7-day baseline to distinguish leaks from normal working-set growth
- [x] T017 [US2] In `src/pmmcp/prompts/specialist.py`, add baseline-aware heuristic to Disk domain_knowledge: check whether I/O spikes recur at the same time daily (scheduled jobs like backups, log rotation)
- [x] T018 [US2] In `src/pmmcp/prompts/specialist.py`, add baseline-aware heuristic to Network domain_knowledge: check whether current packet drop rate is within normal variance over the past week; and Process domain_knowledge: check whether process count and context switch rate match the 7-day pattern before flagging runaway processes
- [x] T019 [US2] Run tests and confirm they PASS (GREEN): `uv run pytest tests/unit/test_prompts_specialist.py -v` — commit implementation

**Checkpoint**: All 5 domain specialists have baseline-aware heuristics. Worktree A pre-push sanity check.

---

## Phase 5: User Story 5 — Graceful degradation when baseline data is insufficient (Priority: P2)

**Goal**: Add fallback instructions to the Baseline step so specialists degrade gracefully when historical data is missing or sparse.

**Independent Test**: Verify the specialist prompt includes fallback guidance for insufficient baseline data.

**Worktree**: A (same worktree as US1/US2 — modifies the Baseline step text added in US1)

> **Note**: US5 is prioritised before US3/US4 because it modifies the same Baseline step text from US1, and completing it in the same worktree avoids merge conflicts.

### Tests for User Story 5 *(required per Principle II — Testing Standards)*

- [x] T020 [US5] Write test in `tests/unit/test_prompts_specialist.py` asserting that `_specialist_investigate_impl()` output for domain subsystems includes instructions to fall back to threshold-only analysis if `pcp_detect_anomalies` returns insufficient data
- [x] T021 [US5] Write test in `tests/unit/test_prompts_specialist.py` asserting that `_specialist_investigate_impl()` output for domain subsystems includes instructions to note "insufficient baseline" or similar limitation wording in the report when degraded
- [x] T022 [US5] Run tests and confirm they FAIL (RED): `uv run pytest tests/unit/test_prompts_specialist.py -v -k "degradation or fallback or insufficient"` — commit failing tests

### Implementation for User Story 5

- [x] T023 [US5] In `src/pmmcp/prompts/specialist.py`, add graceful degradation instructions to the Baseline step: (1) if `pcp_detect_anomalies` returns insufficient data, fall back to threshold-only analysis; (2) note "insufficient baseline data, falling back to threshold-only analysis" in the report; (3) if data is sparse (gaps from restarts), attempt detection but note reduced confidence; (4) if 0 days of history, skip Baseline entirely
- [x] T024 [US5] Run tests and confirm they PASS (GREEN): `uv run pytest tests/unit/test_prompts_specialist.py -v` — commit implementation
- [x] T025 [US5] Run pre-push sanity for Worktree A: `scripts/pre-push-sanity.sh` — all lint, format, and tests must pass. Push Worktree A branch.

**Checkpoint**: Worktree A complete (US1+US2+US5). All domain specialist prompt changes done. Merge to feature branch before starting Worktree B.

---

## Phase 6: User Story 3 — Cross-cutting specialist prioritises by classification (Priority: P2)

**Goal**: Update cross-cutting specialist domain knowledge to prioritise ANOMALY-classified findings and flag correlated anomalies across subsystems.

**Independent Test**: Render the cross-cutting specialist prompt and verify it references classification-based prioritisation and correlated anomaly detection.

**Worktree**: B (cross-cutting + coordinator — separate from Worktree A)

### Tests for User Story 3 *(required per Principle II — Testing Standards)*

- [x] T026 [P] [US3] Write test in `tests/unit/test_prompts_specialist.py` asserting that `_specialist_investigate_impl(subsystem="crosscutting")` output includes guidance to prioritise ANOMALY-classified findings over RECURRING or BASELINE
- [x] T027 [P] [US3] Write test in `tests/unit/test_prompts_specialist.py` asserting that `_specialist_investigate_impl(subsystem="crosscutting")` output includes guidance to flag correlated anomalies across multiple subsystems at the same timestamp
- [x] T028 [P] [US3] Write test in `tests/unit/test_prompts_specialist.py` asserting that `_specialist_investigate_impl(subsystem="crosscutting")` output includes guidance to note when one subsystem reports BASELINE while another reports ANOMALY
- [x] T029 [US3] Run tests and confirm they FAIL (RED): `uv run pytest tests/unit/test_prompts_specialist.py -v -k "crosscutting_classification or crosscutting_priorit"` — commit failing tests

### Implementation for User Story 3

- [x] T030 [US3] In `src/pmmcp/prompts/specialist.py`, update the crosscutting entry in `_SPECIALIST_KNOWLEDGE` domain_knowledge to: (1) prioritise ANOMALY findings over RECURRING/BASELINE, (2) flag correlated anomalies across subsystems at the same timestamp with higher confidence, (3) note when one subsystem reports BASELINE while another reports ANOMALY (the anomaly is more likely root cause)
- [x] T031 [US3] Run tests and confirm they PASS (GREEN): `uv run pytest tests/unit/test_prompts_specialist.py -v` — commit implementation

**Checkpoint**: Cross-cutting specialist now consumes and prioritises by classification.

---

## Phase 7: User Story 4 — Coordinator synthesis weights findings by classification (Priority: P2)

**Goal**: Update coordinator synthesis phase to rank ANOMALY above BASELINE/RECURRING, call out baseline behaviour, and highlight recurring pattern matches.

**Independent Test**: Render the `coordinate_investigation` prompt and verify the synthesis section references classification weighting.

**Worktree**: B (same worktree as US3 — different file: coordinator.py)

### Tests for User Story 4 *(required per Principle II — Testing Standards)*

- [x] T032 [P] [US4] Write test in `tests/unit/test_prompts_coordinator.py` asserting that `_coordinate_investigation_impl()` output includes guidance to rank ANOMALY findings above BASELINE/RECURRING regardless of severity, with severity as secondary sort within each tier
- [x] T033 [P] [US4] Write test in `tests/unit/test_prompts_coordinator.py` asserting that `_coordinate_investigation_impl()` output includes guidance to explicitly call out findings that are normal behaviour for the host
- [x] T034 [P] [US4] Write test in `tests/unit/test_prompts_coordinator.py` asserting that `_coordinate_investigation_impl()` output includes guidance to highlight when an apparent anomaly matches a known recurring pattern
- [x] T035 [US4] Run tests and confirm they FAIL (RED): `uv run pytest tests/unit/test_prompts_coordinator.py -v -k "classification_ranking or baseline_callout or recurring_pattern"` — commit failing tests

### Implementation for User Story 4

- [x] T036 [US4] In `src/pmmcp/prompts/coordinator.py`, update the synthesis section to: (1) rank ANOMALY above BASELINE/RECURRING regardless of severity, severity as secondary sort within each tier; (2) explicitly call out findings that are normal behaviour; (3) highlight when an apparent anomaly matches a known recurring pattern
- [x] T037 [US4] In `src/pmmcp/prompts/coordinator.py`, update the output structure template from "Findings by Severity" to "Findings by Classification & Severity" with sections: New Anomalies, Recurring Patterns, Baseline Behaviour (chronic conditions), Normal Operation
- [x] T038 [US4] Run tests and confirm they PASS (GREEN): `uv run pytest tests/unit/test_prompts_coordinator.py -v` — commit implementation
- [x] T039 [US4] Run pre-push sanity for Worktree B: `scripts/pre-push-sanity.sh` — all lint, format, and tests must pass. Push Worktree B branch.

**Checkpoint**: Worktree B complete (US3+US4). Merge to feature branch.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Documentation updates, final validation, cleanup.

- [x] T040 [P] Update `docs/investigation-flow.md`: change specialist workflow diagram from 4-step to 5-step (Discover → Baseline → Fetch → Analyse → Report), note cross-cutting does NOT include Baseline step, update the sequence diagram to show the Baseline step with `pcp_fetch_timeseries` and `pcp_detect_anomalies` calls, update the "Specialist Workflow" prose section
- [x] T041 [P] Update `docs/investigation-flow.md`: update the Synthesis Phase section to reference classification-based ranking (ANOMALY > RECURRING > BASELINE) and the new output structure
- [x] T042 [P] Review `README.md` for documentation impact — update the specialist workflow description in the prompt table if it references the 4-step flow, and update tool count / prompt descriptions if affected
- [x] T043 Run full test suite with coverage: `uv run pytest --cov=pmmcp --cov-report=term-missing --cov-fail-under=80` — confirm ≥ 80% coverage maintained
- [x] T044 Run final pre-push sanity: `scripts/pre-push-sanity.sh` — lint, format, all tests green
- [x] T045 Run quickstart.md validation: execute the verification commands from `specs/011-specialist-baselining/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — confirm green baseline
- **Phases 3-5 (US1+US2+US5)**: Worktree A — sequential within worktree (same file), can start after Phase 1
- **Phases 6-7 (US3+US4)**: Worktree B — can start after Worktree A merges (US3 tests assert on classification fields added by US1)
- **Phase 8 (Polish)**: After both worktrees merged

### Worktree Strategy

```
main (or feature branch)
 │
 ├── Worktree A: US1 → US2 → US5 (specialist.py — domain specialists)
 │   └── merge back after T025
 │
 └── Worktree B: US3 → US4 (specialist.py crosscutting + coordinator.py)
     └── merge back after T039

 → Phase 8: Polish (docs, README, final validation)
```

### Within Each User Story

- Tests MUST be written and FAIL before implementation (Red-Green-Refactor)
- Commit failing tests, then commit passing implementation as separate commits
- Pre-push sanity MUST pass before pushing each worktree

### Parallel Opportunities

- **T026, T027, T028**: US3 tests can be written in parallel (different test functions, no dependencies)
- **T032, T033, T034**: US4 tests can be written in parallel (different test functions, no dependencies)
- **T040, T041, T042**: Polish documentation tasks can be done in parallel (different files/sections)
- **Worktrees A and B**: Worktree B can begin setup while Worktree A is in final pre-push, but tests should run after Worktree A merge

---

## Parallel Example: Worktree A

```bash
# Story 1: Write all failing tests, then implement
# (sequential — tests and impl touch same file sections)

# Story 2: Write all failing tests, then implement per-subsystem
# T015-T018 modify different subsystem entries in _SPECIALIST_KNOWLEDGE
# but are in the same file — implement sequentially to avoid merge issues

# Story 5: Write failing tests, implement degradation, pre-push sanity
```

## Parallel Example: Worktree B

```bash
# US3 tests can be written in parallel:
Task: "T026 — cross-cutting classification prioritisation test"
Task: "T027 — correlated anomaly detection test"
Task: "T028 — mixed classification guidance test"

# US4 tests can be written in parallel:
Task: "T032 — classification ranking test"
Task: "T033 — baseline behaviour call-out test"
Task: "T034 — recurring pattern highlighting test"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Confirm green baseline
2. Complete Phase 3: US1 — Baseline step + classification fields
3. **STOP and VALIDATE**: Run specialist tests, verify baseline step renders for all 5 domain subsystems
4. This alone delivers the core value: classification in specialist output

### Incremental Delivery

1. US1 → Baseline step and classification fields (core value)
2. US2 → Domain heuristics reference baseline (prevents false threshold alarms)
3. US5 → Graceful degradation (handles edge cases)
4. US3 → Cross-cutting prioritises by classification (correlation layer)
5. US4 → Coordinator ranks by classification (synthesis layer)
6. Polish → Documentation catches up

### Worktree Strategy (Recommended)

With parallel execution capacity:

1. **Worktree A**: US1 → US2 → US5 (all specialist.py domain specialist changes)
2. Merge Worktree A
3. **Worktree B**: US3 → US4 (cross-cutting + coordinator)
4. Merge Worktree B
5. **Main**: Phase 8 polish (docs, README review)

---

## Notes

- All changes are prompt text modifications — no new Python functions, classes, or modules
- No new dependencies — `pyproject.toml` unchanged
- No interface changes — function signatures for `specialist_investigate` and `coordinate_investigation` are unchanged
- Existing contract tests in `tests/contract/test_prompts.py` should continue to pass without modification
- [P] tasks = different files or test functions, no dependencies
- [Story] label maps task to specific user story for traceability
- Pre-push sanity MUST pass before pushing each worktree: `scripts/pre-push-sanity.sh`
