# Feature Specification: pmlogsynth Integration

**Feature Branch**: `004-pmlogsynth-integration`
**Created**: 2026-03-03
**Status**: Draft
**Input**: Integrate pmlogsynth as a containerised archive generator to pre-populate valkey with realistic synthetic performance data before pmproxy starts serving, enabling deterministic E2E test assertions and better pmmcp demonstration.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Realistic Data on Stack Startup (Priority: P1)

A developer runs the local container stack and immediately has realistic performance data available — CPU spikes, memory pressure, disk activity — without manually crafting any data or running any setup steps. pmmcp tools return meaningful results from the first query.

**Why this priority**: Without data, every pmmcp tool returns empty results, making it impossible to demonstrate value or write any non-trivial E2E test. This is the foundation everything else depends on.

**Independent Test**: Can be fully tested by running `podman compose up -d` and querying pmmcp tools — any tool that would normally return empty now returns populated results.

**Acceptance Scenarios**:

1. **Given** an empty valkey instance, **When** `podman compose up` completes, **Then** pmmcp tools return non-empty results for at least CPU, memory, and disk metrics over a historical time range.
2. **Given** the stack is running, **When** a developer queries for series data, **Then** results include realistic metric values with timestamps spanning multiple minutes.
3. **Given** a clean checkout with no existing data, **When** the stack starts, **Then** no manual setup steps are required — data is present automatically.

---

### User Story 2 - Deterministic E2E Test Assertions (Priority: P2)

A developer writes E2E tests that assert on known metric names, value ranges, and time windows derived from the synthetic data profiles. Tests pass consistently across environments because the data is generated from source-controlled profiles.

**Why this priority**: The core value of synthetic seeding is reproducibility. Once data is present (P1), being able to assert on its known shape unlocks the full E2E testing capability.

**Independent Test**: Can be fully tested by writing an E2E test that asserts a specific metric exists and has values within a known range, then running it on two separate machines to confirm identical results.

**Acceptance Scenarios**:

1. **Given** a profile defining a CPU spike at a known relative time offset, **When** E2E tests query using a wide time window that encompasses the full archive span plus a generous buffer (e.g., archive covers 60 min of data → test queries `-90minutes` to `now`), **Then** the spike is detected within the returned results regardless of startup drift.
2. **Given** the same profile is used on two different machines, **When** both run the full stack, **Then** E2E test assertions pass on both without modification.
3. **Given** a profile is updated, **When** the stack is restarted, **Then** the new data pattern is available without any additional steps.

**Note on time window strategy**: Generated archives carry wall-clock timestamps from container runtime. Tests MUST use query windows wider than the archive's data span to tolerate non-deterministic compose startup drift. Exact spike timestamps are not asserted — instead tests assert that a spike *pattern* (value exceeding a threshold) exists somewhere within the wide window. This intentionally tests the fuzzy pattern-finding capability of pmmcp tools.

---

### User Story 3 - Developer Adds a New Profile (Priority: P3)

A developer creates a new workload profile to cover a scenario not in the existing set (e.g., a multi-host fleet view), drops it in the profiles directory, and the next `podman compose up` includes the new data automatically.

**Why this priority**: Extensibility. Once the pipeline exists, profiles are the primary lever developers use — new scenarios should require zero infrastructure changes.

**Independent Test**: Can be fully tested by adding a new `.yml` profile file and confirming its generated data is queryable after stack restart.

**Acceptance Scenarios**:

1. **Given** a valid profile YAML file placed in the `profiles/` directory, **When** the stack starts, **Then** metric data from that profile is available for querying.
2. **Given** a profile with invalid syntax, **When** the stack starts, **Then** the startup logs surface a clear error identifying the offending profile, and the rest of the profiles are still processed.

---

### Edge Cases

- What happens when all profiles fail to generate archives? Stack should still start; data is simply absent with a logged warning.
- What happens when the archive volume already contains stale archives from a previous run? New generation always overwrites them unconditionally — every `compose up` starts from a known clean state.
- What happens to the archives volume when the stack is torn down? `podman compose down` MUST include volume removal (equivalent to `--volumes`) to leave no orphaned data behind.
- What happens if the seeding step runs before the data store is fully ready to accept connections? The seeder retries until the store is ready, up to a maximum of 60 seconds, then exits non-zero (failing the compose startup).
- What happens when a profile generates zero metrics? The archive is still valid and the seeder loads it without error (it just has no data).
- What happens if pmseries --load fails for an individual archive? The seeder exits non-zero immediately — all-or-nothing. Partial data causes silent test gaps that are harder to debug than a loud startup failure.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The container stack MUST include an archive-generation stage that runs before the data store is seeded, using profile files as input.
- **FR-002**: Profile files MUST be stored in a source-controlled directory (`profiles/`) and treated as the single source of truth for synthetic data shape.
- **FR-003**: Generated archives MUST NOT be committed to version control — they are ephemeral build artifacts.
- **FR-004**: The seeding stage MUST wait for both the archive-generation stage to complete and the data store to be ready before loading data.
- **FR-005**: The main PCP/pmproxy service MUST NOT start until seeding is complete, ensuring data is available from the first query.
- **FR-006**: The archive-generation tooling MUST run entirely inside a container — no host machine dependency on PCP binaries or Python PCP bindings.
- **FR-007**: Adding a new profile MUST require only placing a valid YAML file in the `profiles/` directory — no changes to container configuration, compose files, or CI scripts.
- **FR-008**: The initial profile set MUST include at minimum: a steady-state workload profile (CPU, memory, disk, network) and an anomaly/spike profile, matching the scenarios exercised by pmmcp's existing tools and prompts.
- **FR-009**: The pmlogsynth library MUST be added as a dev dependency so profile authors can develop and validate profiles locally on machines where PCP Python bindings are available.
- **FR-010**: CI MUST build the archive-generation container image as part of the compose startup step — no pre-built image required.
- **FR-011**: Tearing down the stack MUST remove the archives named volume — no orphaned data left behind between runs.

### Key Entities

- **Workload Profile**: A YAML file describing a synthetic performance scenario. Defines metric names, value shapes, time ranges, and patterns (steady-state, spike, etc.). Lives in `profiles/`, versioned in git.
- **Performance Archive**: A binary representation of performance metric time-series data, generated from a profile. Ephemeral, never committed. Shared between the generator and seeder via a named volume.
- **Archive-Generation Container**: A one-shot container that reads all profiles and writes archives to the shared volume, then exits. Built from the PCP base image with pmlogsynth added.
- **Seeder Container**: A one-shot container that loads all generated archives into the running data store, then exits. Uses the standard PCP image with pmseries tooling.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After `podman compose up` completes, all pmmcp tools that query time-series data return non-empty results without any manual developer intervention.
- **SC-002**: E2E tests can assert on specific named metrics and value ranges with a false-positive rate of zero across at least two different environments (macOS developer machine via VM, GitHub Actions CI).
- **SC-003**: A developer with no prior knowledge of the archive-generation pipeline can add a new profile and have its data available in the stack within one compose restart — with no file changes outside `profiles/`.
- **SC-004**: Stack startup time (from `podman compose up` invocation to pmproxy being ready with data) increases by no more than 60 seconds compared to the current stack without seeding.
- **SC-005**: The existing unit and integration test suites pass without modification — the synthetic data pipeline is purely additive to the dev/CI environment.

## Assumptions

- pmlogsynth is available from its git repository and can be installed via pip in the PCP base container image.
- The PCP base image (`quay.io/performancecopilot/pcp:latest`) includes `pmseries` and the necessary tooling to load archives into a Redis-compatible data store.
- Profile YAML files follow the schema expected by pmlogsynth's `generate` command — no custom format translation is required.
- The data store (valkey/redis-stack) is accessible by hostname within the compose network.
- Archives are identified by the `.0` extension convention used by PCP archive naming.
- macOS developers run the container stack on a Linux VM (as per existing project setup); pmlogsynth's optional dev dependency may not be importable on macOS directly, which is acceptable.

## Clarifications

### Session 2026-03-03

- Q: Should the generator always regenerate archives on every compose up, or skip if archives already exist? → A: Always regenerate — unconditionally overwrite on every startup for a known clean state. Stack teardown also purges the archives volume.
- Q: If pmseries --load fails for one archive, should the seeder fail fast or continue with remaining archives? → A: Fail fast — all-or-nothing. Partial data causes silent gaps harder to debug than a loud startup failure.
- Q: How long should the seeder wait for the data store to be ready before failing? → A: 60 seconds maximum, then exit non-zero.
- Q: How should E2E tests specify query windows to reliably capture generated archive data despite non-deterministic startup timing? → A: Use wide query windows wider than the full archive span plus a generous buffer. Tests assert that a spike *pattern* exists somewhere in the window, not at an exact timestamp — intentionally testing the fuzzy pattern-finding capability.

## Out of Scope

- Generating data for multi-host fleet scenarios (deferred to a future profile addition).
- Pinning pmlogsynth to a tagged release (currently tracks `@main`; pinning deferred until releases exist).
- AI-based profile generation integration.
- Any changes to pmmcp's runtime behaviour or MCP tool implementations.
