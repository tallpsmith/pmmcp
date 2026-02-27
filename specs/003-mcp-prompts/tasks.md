# Tasks: MCP Prompts — Investigation Workflow Templates

**Input**: Design documents from `/specs/003-mcp-prompts/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅

**Tests**: Per the project constitution (Principle II — Testing Standards, NON-NEGOTIABLE), tests
are mandatory. Unit coverage MUST reach ≥ 80% and contract tests MUST accompany any interface
change. Test tasks shown below MUST be written first and confirmed FAILING before implementation
begins (Red-Green-Refactor cycle).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing
of each story. Stories MUST be worked one at a time — finish and push one before starting the next
(Constitution v1.2.0, Principle II).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to
- Exact file paths are included in all descriptions

---

## Phase 1: Setup & Foundation

**Purpose**: Create the prompts package skeleton and server registration hook. This is the only
blocking prerequisite — no user story work can begin until both tasks are complete.

**Commit**: `chore: add prompts package skeleton and server registration hook`

- [ ] T001 Create empty package init at src/pmmcp/prompts/__init__.py
- [ ] T002 Add `import pmmcp.prompts  # noqa: E402, F401` side-effect import to src/pmmcp/server.py (after existing `import pmmcp.tools` line)

**Checkpoint**: Package is importable; server registration hook exists. User story work can now begin.

---

## Phase 2: User Story 1 — Guided Subsystem Investigation (Priority: P1) 🎯 MVP

**Goal**: Expose `investigate_subsystem` prompt covering all 6 subsystems (cpu, memory, disk,
network, process, general) with discovery-first workflow, subsystem hints, presentation standards,
and guard clauses for missing tools / no metrics / out-of-retention timerange. Retire
`performance-investigator.md` and `metric-explorer.md` agents.

**Independent Test**: Request `investigate_subsystem` for each of the 6 subsystem values; verify
each returns ≥1 message containing discovery-first instruction, natural-language namespace hints,
presentation standards, and all required guard-clause keywords.

### Tests for User Story 1 *(write first — confirm RED before implementing)*

- [ ] T003 [P] [US1] Write failing unit tests for `_investigate_subsystem_impl` covering all FR-003–FR-005, FR-013–FR-014, FR-017–FR-019 assertions in tests/unit/test_prompts_investigate.py
- [ ] T004 [P] [US1] Write failing contract tests for `investigate_subsystem` (schema + non-empty message list) in tests/contract/test_prompts.py

> **Commit after RED confirmed**: `test: add failing tests for investigate_subsystem prompt`

### Implementation for User Story 1

- [ ] T005 [US1] Implement `_investigate_subsystem_impl` and `@mcp.prompt() investigate_subsystem` with all workflow phases, subsystem hints, and guard clauses in src/pmmcp/prompts/investigate.py
- [ ] T006 [US1] Add `from pmmcp.prompts import investigate  # noqa: F401` to src/pmmcp/prompts/__init__.py
- [ ] T007 [P] [US1] Delete agents/performance-investigator.md (content migrated to investigate.py)
- [ ] T008 [P] [US1] Delete agents/metric-explorer.md (content migrated to investigate.py)

> **Commit after GREEN + pre-push-sanity**: `feat: implement investigate_subsystem prompt + retire performance-investigator and metric-explorer agents`

**Checkpoint**: `investigate_subsystem` is registered, all unit + contract tests pass, both agent files are gone.

---

## Phase 3: User Story 2 — Live Incident Triage (Priority: P2)

**Goal**: Expose `incident_triage` prompt with symptom-to-subsystem mapping, host-specific vs
fleet-wide scope confirmation, general-sweep fallback for unmappable symptoms, and guard clauses
for missing tools / out-of-retention timerange. No agent to retire (wholly new capability).

**Independent Test**: Invoke `incident_triage` with a symptom string; verify the returned message
contains symptom-to-subsystem mapping guidance, fleet/host scope confirmation instruction, general
sweep fallback for ambiguous symptoms, and required guard clauses — without requiring any other
prompt to be present.

### Tests for User Story 2 *(write first — confirm RED before implementing)*

- [ ] T009 [P] [US2] Write failing unit tests for `_incident_triage_impl` covering FR-010–FR-012, FR-017, FR-019, FR-022 assertions in tests/unit/test_prompts_triage.py
- [ ] T010 [P] [US2] Add failing `incident_triage` contract assertions (schema + message structure) to tests/contract/test_prompts.py

> **Commit after RED confirmed**: `test: add failing tests for incident_triage prompt`

### Implementation for User Story 2

- [ ] T011 [US2] Implement `_incident_triage_impl` and `@mcp.prompt() incident_triage` with symptom mapping table, scope confirmation, general-sweep fallback, and all guard clauses in src/pmmcp/prompts/triage.py
- [ ] T012 [US2] Add `from pmmcp.prompts import triage  # noqa: F401` to src/pmmcp/prompts/__init__.py

> **Commit after GREEN + pre-push-sanity**: `feat: implement incident_triage prompt`

**Checkpoint**: `incident_triage` is registered, all unit + contract tests pass, no severity parameter present (confirmed removed).

---

## Phase 4: User Story 3 — Before/After Period Comparison (Priority: P2)

**Goal**: Expose `compare_periods` prompt with broad-scan-first methodology, magnitude-ranked
results, root-cause hypothesis, overlap detection guard clause, and out-of-retention guard clause.
Retire `performance-comparator.md` agent.

**Independent Test**: Invoke `compare_periods` with two non-overlapping time windows; verify the
returned message instructs broad scan first, ranking by magnitude, root-cause hypothesis, overlap
detection with stop-on-overlap behaviour, and out-of-retention guard clause.

### Tests for User Story 3 *(write first — confirm RED before implementing)*

- [ ] T013 [P] [US3] Write failing unit tests for `_compare_periods_impl` covering FR-006–FR-007, FR-017, FR-019–FR-020 assertions in tests/unit/test_prompts_compare.py
- [ ] T014 [P] [US3] Add failing `compare_periods` contract assertions (schema + message structure) to tests/contract/test_prompts.py

> **Commit after RED confirmed**: `test: add failing tests for compare_periods prompt`

### Implementation for User Story 3

- [ ] T015 [US3] Implement `_compare_periods_impl` and `@mcp.prompt() compare_periods` with overlap detection, broad-scan instruction, magnitude ranking, root-cause hypothesis, and all guard clauses in src/pmmcp/prompts/compare.py
- [ ] T016 [US3] Add `from pmmcp.prompts import compare  # noqa: F401` to src/pmmcp/prompts/__init__.py
- [ ] T017 [P] [US3] Delete agents/performance-comparator.md (content migrated to compare.py)

> **Commit after GREEN + pre-push-sanity**: `feat: implement compare_periods prompt + retire performance-comparator agent`

**Checkpoint**: `compare_periods` is registered, all unit + contract tests pass, performance-comparator agent is gone.

---

## Phase 5: User Story 4 — Fleet-Wide Health Check (Priority: P3)

**Goal**: Expose `fleet_health_check` prompt with host enumeration, no-hosts-found abort, per-host
summary table, default subsystems (cpu/memory/disk/network), detail-level drill-down, and all
guard clauses. Retire `performance-reporter.md` agent.

**Independent Test**: Invoke `fleet_health_check` with default and explicit arguments; verify the
returned message instructs host enumeration first, produces a host-by-subsystem summary table,
handles `detail_level=detailed` drill-down, scopes to provided `subsystems` and `timerange`, and
includes no-hosts-found and out-of-retention guard clauses.

### Tests for User Story 4 *(write first — confirm RED before implementing)*

- [ ] T018 [P] [US4] Write failing unit tests for `_fleet_health_check_impl` covering FR-008–FR-009, FR-017–FR-019, FR-021 assertions in tests/unit/test_prompts_health.py
- [ ] T019 [P] [US4] Add failing `fleet_health_check` contract assertions (schema + message structure) and `test_all_4_prompts_registered` assertion to tests/contract/test_prompts.py

> **Commit after RED confirmed**: `test: add failing tests for fleet_health_check prompt`

### Implementation for User Story 4

- [ ] T020 [US4] Implement `_fleet_health_check_impl` and `@mcp.prompt() fleet_health_check` with host check, summary table instruction, detail-level handling, subsystem/timerange scoping, and all guard clauses in src/pmmcp/prompts/health.py
- [ ] T021 [US4] Finalize src/pmmcp/prompts/__init__.py with all four imports: `from pmmcp.prompts import compare, health, investigate, triage  # noqa: F401`
- [ ] T022 [P] [US4] Delete agents/performance-reporter.md (content migrated to health.py)

> **Commit after GREEN + pre-push-sanity**: `feat: implement fleet_health_check prompt + retire performance-reporter agent`

**Checkpoint**: All four prompts registered. Full unit + contract test suite passes. All four agent files are gone. Coverage ≥ 80%.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and audit of migrated content

- [ ] T023 Run scripts/pre-push-sanity.sh for final lint + format + test pass with coverage ≥ 80% confirmed
- [ ] T024 [P] Audit agent content migration — verify investigation patterns, metric hints, namespace tables, presentation standards, and threshold guidance from all four retired agents are preserved in prompt implementations (SC-004)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **US1 (Phase 2)**: Depends on Phase 1 completion — BLOCKS nothing else but should be done first (P1 priority)
- **US2 (Phase 3)**: Depends on Phase 1 completion — independent of US1, but MUST wait for story-by-story discipline
- **US3 (Phase 4)**: Depends on Phase 1 completion — independent of US1/US2
- **US4 (Phase 5)**: Depends on Phase 1 completion — independent of US1/US2/US3
- **Polish (Phase 6)**: Depends on all four user stories complete

> ⚠️ Per Constitution v1.2.0 Principle II: Stories MUST be worked one at a time in priority order. Finish and push each story before starting the next.

### User Story Dependencies

- **US1 (P1)**: Starts after Phase 1 — no dependency on other stories
- **US2 (P2)**: Starts after Phase 1 and US1 completion — no content dependency on US1
- **US3 (P2)**: Starts after Phase 1 and US2 completion — no content dependency on US1/US2
- **US4 (P3)**: Starts after Phase 1 and US3 completion — no content dependency on prior stories

### Within Each User Story

1. Tests MUST be written first and confirmed FAILING (RED)
2. Tests committed before implementation begins
3. Implementation makes tests GREEN
4. Pre-push sanity check (lint + format + tests) passes
5. Implementation + agent deletion committed and pushed

### Parallel Opportunities Within Each Story

- **Test tasks [P]**: unit test file and contract test file are different → write both simultaneously
- **Agent deletion tasks [P]**: independent files → delete both simultaneously (US1: T007+T008)
- **Implementation + agent deletion**: implementation completes first, then deletions can proceed alongside __init__.py update for US1

---

## Parallel Execution Examples

### User Story 1 Test Phase (T003 || T004)

```
Parallel: write test_prompts_investigate.py (T003) + write test_prompts.py (T004)
Sequential: commit RED, then start T005
```

### User Story 1 Retire Phase (T007 || T008)

```
Parallel: delete performance-investigator.md (T007) + delete metric-explorer.md (T008)
Sequential: after T005+T006 implement and import are confirmed green
```

### User Story 3 (T013 || T014; T015 → T016 → T017)

```
Parallel:  write test_prompts_compare.py (T013) + extend test_prompts.py (T014)
Sequential: T015 implement → T016 add import → T017 delete agent
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T002)
2. Write failing tests (T003–T004) → commit RED
3. Implement (T005–T008) → confirm GREEN → pre-push sanity
4. **STOP and VALIDATE**: `investigate_subsystem` is discoverable, tests pass, agents retired
5. Push and demo MVP to stakeholder

### Incremental Delivery (Full Feature)

1. Phase 1: Setup → prompts package skeleton ready
2. US1 → `investigate_subsystem` live, agents retired → push (MVP)
3. US2 → `incident_triage` live → push
4. US3 → `compare_periods` live, comparator agent retired → push
5. US4 → `fleet_health_check` live, reporter agent retired → push (complete feature)
6. Polish → audit + final sanity → push

Each story adds a new prompt without breaking the previous ones. After US4, all four prompts are
discoverable, all four agent files are gone, and coverage ≥ 80% is confirmed.

---

## Notes

- [P] tasks = different files, no shared state — safe to execute simultaneously
- [US*] label maps task to spec.md user story for traceability
- Stories MUST complete full Red-Green-Refactor before the next begins (Constitution v1.2.0)
- Each story produces exactly two commits: `test: ...` then `feat: ...`
- Pre-push sanity MUST pass before every `git push` (`scripts/pre-push-sanity.sh`)
- E2E tests for prompt workflows are explicitly deferred pending `pmlogger-synth` (issue #13)
- `test_all_4_prompts_registered` contract assertion is added in T019 (US4) since all four prompts must exist for it to pass
