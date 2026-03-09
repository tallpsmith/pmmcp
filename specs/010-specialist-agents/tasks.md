# Tasks: Specialist Agent Investigation Coordinator

**Input**: Design documents from `/specs/010-specialist-agents/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: Per the project constitution (Principle II — Testing Standards, NON-NEGOTIABLE), tests
are mandatory. Unit coverage MUST reach ≥ 80% and contract tests MUST accompany any interface
change. The test tasks shown below MUST be included; adjust scope and file paths to match the
feature's specific contracts and user stories.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: No new dependencies or project structure changes needed — this feature is pure prompt-layer work atop the existing codebase. Setup is limited to verifying the branch and existing prompt infrastructure.

- [x] T001 Verify branch `010-specialist-agents` is clean and based on latest `main`
- [x] T002 Run `uv sync --extra dev` and confirm existing test suite passes

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The `_SPECIALIST_KNOWLEDGE` data structure is shared by both the specialist prompt (US3) and the coordinator prompt (US1). It must exist before either can be implemented.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Tests for Foundational Phase *(required per Principle II)*

- [x] T003 [P] Write unit tests for `_SPECIALIST_KNOWLEDGE` structure validation in `tests/unit/test_prompts_specialist.py` — assert all 6 subsystem keys exist (cpu, memory, disk, network, process, crosscutting), each entry has `prefix`, `display_name`, `domain_knowledge`, `report_guidance` fields, and `domain_knowledge` contains ≥5 investigation heuristics

### Implementation for Foundational Phase

- [x] T004 Create `src/pmmcp/prompts/specialist.py` with `_SPECIALIST_KNOWLEDGE` dict containing all 6 subsystem entries. Each entry: `prefix` (str|None), `display_name` (str), `domain_knowledge` (str — 5-8 concrete investigation heuristics per R3), `report_guidance` (str — per-finding structure per R6). Subsystem keys: cpu, memory, disk, network, process, crosscutting
- [x] T005 Register specialist module in `src/pmmcp/prompts/__init__.py` — add `import pmmcp.prompts.specialist` side-effect import

**Checkpoint**: `_SPECIALIST_KNOWLEDGE` is importable and passes structural validation tests

---

## Phase 3: User Story 3 — Specialist Domain Prompts (Priority: P2) 🎯 MVP

**Goal**: Each subsystem gets a `specialist_investigate` prompt encoding deep sysadmin domain knowledge — not namespace hints, but the reasoning of an experienced performance engineer.

**Independent Test**: Render each specialist prompt variant and verify it contains domain-specific investigation logic, metric relationships, and interpretation guidance unique to that subsystem.

**Why this before US1**: US1 (coordinator) dispatches specialists — those specialists must exist first. US3 is the building block.

### Tests for User Story 3 *(required per Principle II)*

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation (Red-Green-Refactor)**

- [x] T006 [P] [US3] Unit tests for `_specialist_investigate_impl()` in `tests/unit/test_prompts_specialist.py` — test each subsystem returns `list[dict]` with role="user", content is non-empty string, content contains subsystem-specific keywords (e.g. CPU: "steal time", "runqueue"; Memory: "swap", "OOM"; Disk: "IOPS", "queue"; Network: "dropped", "bandwidth"; Process: "zombie", "context switch"; Crosscutting: "pcp_quick_investigate")
- [x] T007 [P] [US3] Unit test for invalid subsystem — `_specialist_investigate_impl("bogus", ...)` returns an error message (not an exception)
- [x] T008 [P] [US3] Unit test that specialist prompt mandates `pcp_discover_metrics(prefix=)` as primary discovery mechanism per FR-008 — content mentions `pcp_discover_metrics` for subsystems with a prefix
- [x] T009 [P] [US3] Unit test that optional parameters (request, host, time_of_interest, lookback) are interpolated into the prompt content when provided

### Implementation for User Story 3

- [x] T010 [US3] Implement `_specialist_investigate_impl(subsystem, request, host, time_of_interest, lookback)` in `src/pmmcp/prompts/specialist.py` — guard clause for invalid subsystem, interpolate specialist knowledge + parameters into structured investigation prompt, return `list[dict]` per MCP prompt pattern
- [x] T011 [US3] Implement `@mcp.prompt() specialist_investigate(...)` wrapper in `src/pmmcp/prompts/specialist.py` — delegates to `_specialist_investigate_impl()`
- [x] T012 [P] [US3] Contract test: `specialist_investigate` is registered, has correct argument schema (subsystem required; request, host, time_of_interest, lookback optional), returns well-formed messages — in `tests/contract/test_prompts.py`

**Checkpoint**: `specialist_investigate` works for all 6 subsystems with deep domain knowledge

---

## Phase 4: User Story 1 — Parallel Specialist Investigation (Priority: P1)

**Goal**: Coordinator prompt dispatches all 6 specialist sub-agents concurrently (or sequentially as fallback), then synthesises findings into a unified root-cause narrative.

**Independent Test**: Invoke the coordinator prompt and verify it produces dispatch instructions for all six specialists with domain-specific investigation guidance.

### Tests for User Story 1 *(required per Principle II)*

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation (Red-Green-Refactor)**

- [x] T013 [P] [US1] Unit tests for `_coordinate_investigation_impl()` in `tests/unit/test_prompts_coordinator.py` — test returns `list[dict]` with role="user", content mentions all 6 subsystems (cpu, memory, disk, network, process, crosscutting), content contains `specialist_investigate` dispatch references
- [x] T014 [P] [US1] Unit test that coordinator includes parallel dispatch instructions AND sequential fallback per FR-005 — content contains both "parallel" and "sequential" guidance
- [x] T015 [P] [US1] Unit test that coordinator includes synthesis/cross-referencing instructions per FR-004 — content mentions cross-referencing, correlation, unified narrative
- [x] T016 [P] [US1] Unit test that coordinator handles partial results gracefully per FR-006 — content includes guidance for when some specialists fail or return no data
- [x] T017 [P] [US1] Unit test that optional parameters (request, host, time_of_interest, lookback) are interpolated into the coordinator prompt content

### Implementation for User Story 1

- [x] T018 [US1] Create `src/pmmcp/prompts/coordinator.py` with `_coordinate_investigation_impl(request, host, time_of_interest, lookback)` — generates dispatch instructions for all 6 specialists, parallel + sequential modes, synthesis phase with cross-referencing guidance, partial-result handling. Returns `list[dict]`
- [x] T019 [US1] Implement `@mcp.prompt() coordinate_investigation(...)` wrapper in `src/pmmcp/prompts/coordinator.py` — delegates to `_coordinate_investigation_impl()`
- [x] T020 [US1] Register coordinator module in `src/pmmcp/prompts/__init__.py` — add `import pmmcp.prompts.coordinator` side-effect import
- [x] T021 [P] [US1] Contract test: `coordinate_investigation` is registered, has correct argument schema (request required; host, time_of_interest, lookback optional), returns well-formed messages — in `tests/contract/test_prompts.py`

**Checkpoint**: Coordinator dispatches all 6 specialists with both parallel and sequential modes

---

## Phase 5: User Story 2 — Adequate Metric Coverage During Discovery (Priority: P1)

**Goal**: Bump `pcp_search` default limit from 20→50 so broad searches return metrics across multiple namespaces.

**Independent Test**: Verify `pcp_search` default limit is 50 and specialist prompts guide agents to use namespace-scoped discovery.

### Tests for User Story 2 *(required per Principle II)*

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation (Red-Green-Refactor)**

- [x] T022 [P] [US2] Unit test that `pcp_search` default limit is 50 (not 20) in `tests/unit/test_search.py` — inspect the `_search_impl` function signature or call with no explicit limit and verify the default

### Implementation for User Story 2

- [x] T023 [US2] Change `limit: int = 20` to `limit: int = 50` in `src/pmmcp/tools/search.py` per FR-007

**Checkpoint**: `pcp_search` returns up to 50 results by default

---

## Phase 6: User Story 4 — Coordinator Steers LLM Entry Point (Priority: P3)

**Goal**: Update `session_init` prompt to reference the coordinator as the recommended investigation entry point, and ensure prompt descriptions position the coordinator clearly.

**Independent Test**: Verify session_init mentions the coordinator and prompt descriptions are clear.

### Tests for User Story 4 *(required per Principle II)*

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation (Red-Green-Refactor)**

- [x] T024 [P] [US4] Unit test that `session_init` prompt content references `coordinate_investigation` as investigation entry point — in `tests/unit/test_prompts_session_init.py` or existing test file
- [x] T025 [P] [US4] Contract test that updated prompt count is correct (should now include specialist_investigate + coordinate_investigation) — update `test_all_4_prompts_registered` in `tests/contract/test_prompts.py` to reflect new total

### Implementation for User Story 4

- [x] T026 [US4] Update `src/pmmcp/prompts/session_init.py` — add coordinator reference to session init content per FR-009
- [x] T027 [US4] Update `tests/contract/test_prompts.py` — update the registered-prompt-count assertion to include the 2 new prompts

**Checkpoint**: Session init guides LLMs to use coordinator for broad investigations

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final validation across all stories

- [x] T028 Run full test suite with coverage: `uv run pytest --cov=pmmcp --cov-report=term-missing` — verify ≥80% coverage
- [x] T029 Run lint and format: `uv run ruff check src/ tests/ && uv run ruff format src/ tests/`
- [x] T030 Run `scripts/pre-push-sanity.sh` — full pre-push validation
- [x] T031 Validate against `specs/010-specialist-agents/quickstart.md` — run the quick test commands and verify they pass

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — creates `_SPECIALIST_KNOWLEDGE` shared data
- **US3 — Specialist Prompts (Phase 3)**: Depends on Foundational — implements the specialist prompt using `_SPECIALIST_KNOWLEDGE`
- **US1 — Coordinator (Phase 4)**: Depends on US3 — coordinator dispatches specialists that must exist first
- **US2 — Search Limit (Phase 5)**: Depends on Setup only — independent one-line change, can run in parallel with US3/US1
- **US4 — Session Init (Phase 6)**: Depends on US1 — references coordinator prompt that must be registered
- **Polish (Phase 7)**: Depends on all user stories being complete

### User Story Dependencies

- **US3 (P2)**: Can start after Foundational (Phase 2) — building block for US1
- **US1 (P1)**: Depends on US3 — coordinator dispatches specialists
- **US2 (P1)**: Independent — can start after Setup, parallelizable with US3
- **US4 (P3)**: Depends on US1 — references coordinator

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- `_*_impl()` function before `@mcp.prompt()` wrapper
- Registration before contract tests
- Story complete before moving to next priority

### Parallel Opportunities

- T003 (foundational tests) can run alongside T001-T002 setup
- T006-T009 (US3 tests) are all parallel — different test scenarios, same test file
- T013-T017 (US1 tests) are all parallel — different test scenarios, same test file
- T022 (US2 test) can run in parallel with any US3/US1 work
- T024-T025 (US4 tests) are parallel — different test files

---

## Parallel Example: User Story 3

```bash
# Launch all US3 tests together (all [P]):
Task: T006 "Unit tests for _specialist_investigate_impl() — per-subsystem keywords"
Task: T007 "Unit test for invalid subsystem error handling"
Task: T008 "Unit test specialist mandates pcp_discover_metrics"
Task: T009 "Unit test optional parameter interpolation"

# After tests pass (RED confirmed), implement sequentially:
Task: T010 "Implement _specialist_investigate_impl()"
Task: T011 "Implement @mcp.prompt wrapper"
Task: T012 "Contract test for specialist_investigate registration"
```

---

## Implementation Strategy

### MVP First (US3 + US1)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (`_SPECIALIST_KNOWLEDGE`)
3. Complete Phase 3: US3 — Specialist Prompts (building block)
4. Complete Phase 4: US1 — Coordinator (dispatches specialists)
5. **STOP and VALIDATE**: Both prompts work end-to-end

### Incremental Delivery

1. Setup + Foundational → `_SPECIALIST_KNOWLEDGE` ready
2. Add US3 → Test specialists independently → Commit
3. Add US1 → Test coordinator independently → Commit
4. Add US2 → Test search limit → Commit (can be done earlier in parallel)
5. Add US4 → Test session init update → Commit
6. Polish → Pre-push sanity → Push

### Note on Story Priority vs Dependency Order

US1 (P1) and US3 (P2) have an inverted dependency: the P1 coordinator *dispatches* P2 specialists. Implementation order is US3→US1 despite US1 having higher business priority. US2 (P1) is independent and can slot in anywhere after Setup.

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- No new dependencies — pure prompt-layer work + one default value change
