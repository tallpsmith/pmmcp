# Tasks: Grafana & mcp-grafana Compose Integration

**Input**: Design documents from `/specs/012-grafana-compose/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Per the project constitution (Principle II — Testing Standards, NON-NEGOTIABLE), tests
are mandatory. This feature has no new Python application code, but E2E tests MUST verify that the
compose infrastructure works correctly. E2E pytest tests will use `httpx` to verify Grafana and
mcp-grafana service health after compose stack startup.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create provisioning directory structure and files needed by Grafana

- [x] T001 Create provisioning directory at grafana/provisioning/datasources/
- [x] T002 Create PCP datasource provisioning file at grafana/provisioning/datasources/pcp.yaml with Valkey + Vector datasources pointing at http://pcp:44322 (per research.md R4)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: No blocking prerequisites — provisioning file is created in Phase 1, compose changes are per-story

**⚠️ CRITICAL**: Phase 1 must be complete before user stories begin (provisioning file is mounted by the Grafana service)

**Checkpoint**: Provisioning files ready — user story implementation can now begin

---

## Phase 3: User Story 1 — Grafana with PCP Datasource (Priority: P1) 🎯 MVP

**Goal**: `podman compose up -d` gives a fully wired Grafana instance with PCP datasources auto-provisioned

**Independent Test**: After compose up, Grafana API at `http://localhost:3000/api/datasources` returns the PCP Valkey and Vector datasources with healthy status

### Tests for User Story 1 *(required per Principle II — Testing Standards)*

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation (Red-Green-Refactor)**

- [ ] T003 [P] [US1] E2E test: Grafana accessible and healthy — verify GET http://localhost:3000/api/health returns 200 in tests/e2e/test_grafana.py
- [ ] T004 [P] [US1] E2E test: PCP datasources provisioned — verify GET http://localhost:3000/api/datasources returns both "PCP Valkey" and "PCP Vector" entries in tests/e2e/test_grafana.py
- [ ] T005 [P] [US1] E2E test: PCP Valkey datasource healthy — verify datasource health check endpoint confirms pmproxy connectivity in tests/e2e/test_grafana.py

### Implementation for User Story 1

- [ ] T006 [US1] Add `grafana` service to docker-compose.yml with image `grafana/grafana:latest`, port 3000, GF_INSTALL_PLUGINS (ZIP URL per research.md R3), GF_PLUGINS_ALLOW_LOADING_UNSIGNED_PLUGINS, anonymous auth env vars (per research.md R5), healthcheck (`curl -sf http://localhost:3000/api/health`), volume mount `./grafana/provisioning:/etc/grafana/provisioning:ro`, depends_on `pcp` service_started
- [ ] T007 [US1] Verify: run `podman compose up -d --wait`, confirm Grafana container is healthy, run E2E tests from T003-T005

**Checkpoint**: Grafana is accessible with working PCP datasources — MVP complete

---

## Phase 4: User Story 2 — mcp-grafana Service (Priority: P2)

**Goal**: mcp-grafana runs alongside Grafana, connected via basic auth, accessible on port 8000/sse

**Independent Test**: After compose up, mcp-grafana SSE endpoint at `http://localhost:8000/sse` responds

### Tests for User Story 2 *(required per Principle II — Testing Standards)*

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation (Red-Green-Refactor)**

- [ ] T008 [P] [US2] E2E test: mcp-grafana SSE endpoint responds — verify GET http://localhost:8000/sse returns a valid SSE connection in tests/e2e/test_grafana.py

### Implementation for User Story 2

- [ ] T009 [US2] Add `mcp-grafana` service to docker-compose.yml with image `mcp/grafana`, port 8000, GRAFANA_URL=http://grafana:3000, GRAFANA_USERNAME=admin, GRAFANA_PASSWORD=admin, depends_on `grafana` service_healthy
- [ ] T010 [US2] Verify: run `podman compose up -d --wait`, confirm mcp-grafana container is running, run E2E test from T008

**Checkpoint**: Both Grafana and mcp-grafana are running and wired together

---

## Phase 5: User Story 3 — CI Parity (Priority: P3)

**Goal**: GitHub Actions E2E job starts Grafana services and verifies them before running E2E tests

**Independent Test**: Push branch, CI E2E job starts compose stack with Grafana services, existing E2E tests pass plus new Grafana smoke tests pass

### Tests for User Story 3 *(required per Principle II — Testing Standards)*

> **NOTE: CI parity is validated by the CI run itself — no additional pytest tests needed beyond those already written in US1/US2. The "test" here is that CI passes.**

### Implementation for User Story 3

- [ ] T011 [US3] Add "Wait for Grafana" step to .github/workflows/ci.yml E2E job after the "Wait for pmproxy" step — poll `http://localhost:3000/api/health` until healthy (same pattern as pmproxy wait)
- [ ] T012 [US3] Add `GRAFANA_URL: http://localhost:3000` to the env section of the E2E job in .github/workflows/ci.yml
- [ ] T013 [US3] Verify: run existing E2E tests locally with compose stack to confirm no regressions (SC-005)

**Checkpoint**: CI workflow includes Grafana services and passes all tests

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation updates and final validation

- [ ] T014 [P] Update README.md — add Grafana and mcp-grafana to the services table, document ports (3000, 8000), add Grafana-specific quickstart section
- [ ] T015 [P] Update CLAUDE.md — add Grafana compose gotchas (unsigned plugin, basic auth requirement, GF_INSTALL_PLUGINS ZIP URL pattern) to "E2E Container Gotchas" section
- [ ] T016 [P] Add inline comments to docker-compose.yml for the new grafana and mcp-grafana services explaining key env vars and the auth decision
- [ ] T017 Run quickstart.md validation — execute all steps from specs/012-grafana-compose/quickstart.md against a fresh compose stack and confirm they work

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: N/A — Phase 1 covers setup
- **User Story 1 (Phase 3)**: Depends on Phase 1 (provisioning files exist)
- **User Story 2 (Phase 4)**: Depends on US1 (mcp-grafana needs the grafana service to exist in compose)
- **User Story 3 (Phase 5)**: Depends on US1 + US2 (CI must test the full compose topology)
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Phase 1 — no dependencies on other stories
- **User Story 2 (P2)**: Depends on US1 — mcp-grafana `depends_on` the grafana service
- **User Story 3 (P3)**: Depends on US1 + US2 — CI must reflect the complete compose topology

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Write compose service definition
- Verify with `podman compose up -d --wait` + run E2E tests
- Commit after each task or logical group

### Parallel Opportunities

- T003, T004, T005 (US1 tests) can run in parallel — different test functions, same file
- T014, T015, T016 (Polish docs) can run in parallel — different files
- US1 and US2 tests (T003-T005, T008) can be written in parallel before any implementation

---

## Parallel Example: User Story 1

```bash
# Write all US1 tests in parallel (they go in the same file but are independent functions):
Task: "E2E test: Grafana accessible and healthy in tests/e2e/test_grafana.py"
Task: "E2E test: PCP datasources provisioned in tests/e2e/test_grafana.py"
Task: "E2E test: PCP Valkey datasource healthy in tests/e2e/test_grafana.py"

# Then implement (sequential — single file):
Task: "Add grafana service to docker-compose.yml"
Task: "Verify: compose up + run E2E tests"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Create provisioning files
2. Complete Phase 3: Grafana + PCP datasources in compose
3. **STOP and VALIDATE**: `podman compose up -d`, open http://localhost:3000, verify datasources
4. Commit and push — MVP is usable

### Incremental Delivery

1. Phase 1 (Setup) → provisioning files committed
2. US1 (Grafana + PCP datasources) → compose up gives working Grafana → commit + push
3. US2 (mcp-grafana) → compose up gives both services → commit + push
4. US3 (CI parity) → CI passes with full topology → commit + push
5. Polish → docs updated, quickstart validated → commit + push

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- This feature has **no new Python application code** — all tasks are infrastructure (YAML, CI workflow)
- E2E tests use `httpx` to hit Grafana/mcp-grafana REST APIs from within the existing E2E test framework
- E2E tests are gated by `PMPROXY_URL` env var (same as existing E2E tests) plus new `GRAFANA_URL`
- The PCP plugin is **unsigned** — requires both `GF_INSTALL_PLUGINS` with ZIP URL and `GF_PLUGINS_ALLOW_LOADING_UNSIGNED_PLUGINS`
- Commit after each task or logical group; follow story-by-story development loop from CLAUDE.md
