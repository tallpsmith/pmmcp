---

description: "Task list for pmlogsynth integration feature"
---

# Tasks: pmlogsynth Integration

**Input**: Design documents from `/specs/004-pmlogsynth-integration/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓

**Tests**: Mandatory per Constitution Principle II (TDD — NON-NEGOTIABLE). Each user story phase
begins with failing tests committed before implementation. Red → Green → Refactor.

**Organization**: Infrastructure-only feature. US1 builds the full seeding pipeline; US2 and US3
extend test coverage on top of it. US1 completion is a hard prerequisite for US2/US3 E2E tests.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in all descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add dev dependency before any container or profile work begins.

- [X] T001 Add `pmlogsynth @ git+https://github.com/tallpsmith/pmlogsynth` to `[project.optional-dependencies] dev` group in `pyproject.toml`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: No shared infrastructure layer is independent of US1 for this feature — the compose
pipeline IS User Story 1. T001 is the only prerequisite. Proceed directly to Phase 3.

**⚠️ CRITICAL**: T001 must be complete before any user story work begins.

---

## Phase 3: User Story 1 — Realistic Data on Stack Startup (Priority: P1) 🎯 MVP

**Goal**: Developer runs `podman compose up -d` and immediately gets non-empty pmmcp tool results
for CPU, memory, and disk metrics — no manual data setup required.

**Independent Test**: `PMPROXY_URL=http://localhost:44322 uv run pytest tests/e2e/test_seeded_data.py -m e2e -v`
— all three non-empty assertions pass.

### Tests for User Story 1 — write first, confirm RED before implementing

- [X] T002 [US1] Create `tests/e2e/test_seeded_data.py` with `@pytest.mark.e2e` tests: `test_cpu_metrics_present`, `test_memory_metrics_present`, `test_disk_metrics_present` — each calls `pcp_query_series` for its metric over `-90minutes` to `now` and asserts the result list is non-empty

### Implementation for User Story 1

- [X] T003 [P] [US1] Create `profiles/steady-state.yml` — 60-min profile: 1 phase, CPU `utilization: 0.30` (`user_ratio: 0.70`, `sys_ratio: 0.20`, `iowait_ratio: 0.10`), memory `used_ratio: 0.60 cache_ratio: 0.20`, disk `read_mbps: 10.0 write_mbps: 5.0`, network `rx_mbps: 20.0 tx_mbps: 5.0`, `meta.noise: 0.05`, `meta.interval: 60`
- [X] T004 [P] [US1] Create `profiles/spike.yml` — 60-min profile: 2 phases — baseline 50-min (CPU `utilization: 0.30`, memory `used_ratio: 0.60`) + spike 10-min (`transition: linear`, CPU `utilization: 0.90`, memory `used_ratio: 0.75`), `meta.noise: 0.03`, `meta.interval: 60`
- [X] T005 [P] [US1] Create `generator/Dockerfile` — `FROM quay.io/performancecopilot/pcp:latest` base; `RUN pip install git+https://github.com/tallpsmith/pmlogsynth`; `COPY entrypoint.sh /entrypoint.sh`; `RUN chmod +x /entrypoint.sh`; `ENTRYPOINT ["/entrypoint.sh"]`
- [X] T006 [P] [US1] Create `generator/entrypoint.sh` — glob iterate `/profiles/*.yml`; for each profile derive stem from filename; run `pmlogsynth -o /archives/<stem> <profile>`; on non-zero exit code log `"ERROR: pmlogsynth failed for <profile>"` and exit immediately (fail-fast, FR-007 glob-based, no hardcoded names)
- [X] T007 [US1] Update `docker-compose.yml`: (1) declare `pmmcp-archives` named volume; (2) add `pmlogsynth-generator` service — `build: ./generator`, bind-mount `./profiles:/profiles:ro`, volume-mount `pmmcp-archives:/archives`; (3) add `healthcheck` to `redis-stack` service — `test: ["CMD", "redis-cli", "-p", "6379", "ping"]`, `interval: 5s`, `timeout: 3s`, `retries: 12`; (4) add `pmlogsynth-seeder` service — image `quay.io/performancecopilot/pcp:latest`, volume-mount `pmmcp-archives:/archives:ro`, command iterates `pmseries --load /archives/<stem>/<stem>` fail-fast, `depends_on: pmlogsynth-generator: condition: service_completed_successfully` and `redis-stack: condition: service_healthy`; (5) add `depends_on: pmlogsynth-seeder: condition: service_completed_successfully` to `pcp` service

**Checkpoint**: Run `podman compose up -d` — logs show generator/seeder completing before pcp starts.
Then run E2E tests — T002 test suite passes.

---

## Phase 4: User Story 2 — Deterministic E2E Test Assertions (Priority: P2)

**Goal**: E2E tests assert on known spike and steady-state patterns using wide time windows, with
zero false-positives across environments.

**Independent Test**: `PMPROXY_URL=http://localhost:44322 uv run pytest tests/e2e/test_seeded_data.py -k "spike or steady" -m e2e -v`
— both pattern assertions pass.

### Tests for User Story 2 — write first, confirm RED before checking profile values

- [X] T008 [US2] Add `test_spike_pattern_detected` to `tests/e2e/test_seeded_data.py` — query `kernel.all.cpu.user` using `pcp_fetch_timeseries` with `start="-90minutes"`, assert that at least one returned value exceeds `0.85` (spike phase threshold from `spike.yml`)
- [X] T009 [US2] Add `test_steady_state_cpu_in_baseline_range` to `tests/e2e/test_seeded_data.py` — query `kernel.all.cpu.user` from `steady-state` hostname/source using `pcp_query_series`, assert that the median of returned values falls in the range `[0.20, 0.40]`

### Implementation for User Story 2

*(No new files — US1 profiles already encode the correct thresholds. If tests are red, adjust
`profiles/spike.yml` spike phase `utilization` and/or `profiles/steady-state.yml` baseline
`utilization` to match the assertion thresholds above, then re-run.)*

**Checkpoint**: Both pattern assertion tests pass consistently on a second stack restart.

---

## Phase 5: User Story 3 — Developer Adds a New Profile (Priority: P3)

**Goal**: Dropping any valid YAML into `profiles/` makes its data available after the next stack
restart — zero infrastructure changes required.

**Independent Test**: `PMPROXY_URL=http://localhost:44322 uv run pytest tests/e2e/test_seeded_data.py -k "profiles" -m e2e -v`
— multi-profile assertion passes.

### Tests for User Story 3 — write first, confirm RED before verifying entrypoint

- [X] T010 [US3] Add `test_both_profiles_data_present` to `tests/e2e/test_seeded_data.py` — use `pcp_search` to discover all metric sources; assert at least 2 distinct source hostnames appear (one per profile, each profile sets a unique `meta.hostname`); confirms generator iterated both profiles

### Implementation for User Story 3

- [X] T011 [P] [US3] Review `generator/entrypoint.sh` against FR-007: confirm iteration uses `profiles/*.yml` glob with no hardcoded stems; confirm per-profile failure exits immediately with filename logged; add a `set -euo pipefail` header if absent

**Checkpoint**: Adding any new `.yml` to `profiles/` and restarting the stack makes its metrics
searchable — confirmed by running `test_both_profiles_data_present` (after temporarily adding a
third profile to the `profiles/` directory during manual validation).

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Confirm the seeded pipeline is transparent to the rest of the project.

- [X] T012 [P] Update `CLAUDE.md` "Recent Changes" entry for `004-pmlogsynth-integration` to note compose seeding pipeline is live and `podman compose down --volumes` is required for clean teardown
- [X] T013 [P] Run `scripts/pre-push-sanity.sh` (or `/pre-push-sanity`): confirm lint passes, existing unit/integration test suite is green at ≥80% coverage (SC-005), and note in PR description that E2E tests require live compose stack

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: N/A for this feature
- **User Stories (Phase 3+)**: All depend on T001 (Phase 1)
  - US2 and US3 depend on US1 full completion (E2E tests need live compose stack from US1)
- **Polish (Phase 6)**: Depends on all user stories complete

### User Story Dependencies

- **User Story 1 (P1)**: Depends only on T001. Unblocks US2 and US3.
- **User Story 2 (P2)**: Depends on US1 complete (needs live stack + both profiles)
- **User Story 3 (P3)**: Depends on US1 complete (needs glob-based entrypoint.sh)

### Within Each User Story

1. Write failing tests and commit (`test: <story>`)
2. Implement to make tests pass
3. Refactor if needed (tests stay green)
4. Pre-push sanity → commit + push (`feat: <story>`)

### Parallel Opportunities Within US1

```bash
# After T002 (failing test committed), launch these four together:
T003: Create profiles/steady-state.yml
T004: Create profiles/spike.yml
T005: Create generator/Dockerfile
T006: Create generator/entrypoint.sh

# Then sequentially:
T007: Update docker-compose.yml (single file, all pipeline changes)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: T001 (pyproject.toml)
2. Write failing tests: T002
3. Implement US1: T003–T007 (profiles + generator container + compose wiring)
4. **STOP and VALIDATE**: `podman compose up -d` → `pytest tests/e2e/test_seeded_data.py`
5. Commit and push US1 — stack now has synthetic data on every startup

### Incremental Delivery

1. US1 complete → stack always starts with data (MVP!)
2. US2 → deterministic pattern assertions locked in → CI can assert on data shape
3. US3 → extensibility verified → new profiles just work

### Single-Developer Flow

Work one story at a time (per CLAUDE.md story-by-story loop):

```
T001 → T002 (failing test commit) → T003–T007 (impl) → pass → push
     → T008 (failing test commit) → pass (no extra impl) → push
     → T009 (failing test commit) → pass (verify profile values) → push
     → T010 (failing test commit) → T011 (verify entrypoint) → pass → push
     → T012–T013 (polish) → push
```

---

## Notes

- `[P]` tasks touch different files — safe to implement in one Claude Code session turn
- Tests for US2 have no separate implementation phase: if they go red, fix the profile YAML values
- US3's "implementation" is a review step — `generator/entrypoint.sh` from T006 should already satisfy FR-007; T011 is a confirm-and-harden task
- `podman compose down --volumes` is MANDATORY for clean state — document prominently in PR
- E2E tests skip gracefully when `PMPROXY_URL` is not set; always note this in PR description (SC-005 caveat)
