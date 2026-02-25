# Feature Specification: Integration and End-to-End Test Suites

**Feature Branch**: `002-add-integration-e2e-tests`
**Created**: 2026-02-25
**Status**: Draft
**Input**: User description: "Add integration tests (in-process pmmcp with mock pmproxy) and end-to-end tests (full stack against real PCP) to catch protocol-layer and infrastructure-level regressions not covered by unit tests."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - MCP Protocol Path Verification (Priority: P1)

A developer modifies the server startup code, tool registration, or MCP wrapper layer and wants to know immediately whether all nine tools still dispatch correctly through the real MCP protocol. Currently, unit tests call the implementation functions directly and would not catch a broken tool registration, a misconfigured server lifecycle, or a serialisation error in the MCP response.

Running the integration suite gives the developer a fast, infrastructure-free confirmation that the complete call path — from MCP tool invocation through server dispatch, client initialisation, HTTP interaction with pmproxy, and back to an MCP-formatted response — is working for every tool.

**Why this priority**: This directly addresses the gap in the current test pyramid. The MCP protocol layer is untested. Any regression there would only be discovered when an AI assistant actually tries to use the tool — a much more expensive feedback loop than a CI test.

**Independent Test**: Can be fully tested on any developer machine or CI runner with no external services. Run the integration suite; all nine tools must return well-formed MCP responses against a controlled mock pmproxy.

**Acceptance Scenarios**:

1. **Given** a developer runs the integration test suite with no real PCP or pmproxy available, **When** all tests complete, **Then** all nine MCP tools return valid, well-formed MCP responses and no test requires any external service to be running.
2. **Given** a tool registration is accidentally broken (e.g., wrong decorator argument), **When** the integration suite runs, **Then** the affected test fails with a clear error identifying the broken tool, not a silent pass.
3. **Given** the server lifecycle is disrupted (e.g., `get_client()` returns before the client is initialised), **When** the integration suite runs, **Then** the affected tests fail immediately rather than hanging or producing misleading output.
4. **Given** the integration suite is run in CI alongside unit tests, **When** the pipeline completes, **Then** both suites are reported separately and integration tests do not inflate or deflate unit test coverage figures.

---

### User Story 2 - Full-Stack Regression Detection (Priority: P2)

A developer makes a change that affects how pmmcp launches, how it reads configuration from the environment, or how it serialises responses over the stdio transport. Unit and integration tests pass because they test in-process. But the bug only manifests when pmmcp is launched as a real subprocess — exactly as Claude Desktop or Claude Code would launch it.

The end-to-end suite catches this class of bug by launching pmmcp as a proper subprocess, communicating with it over the stdio MCP transport, and verifying that real metric data flows back through the entire stack: subprocess launch → environment configuration → MCP stdio protocol → pmproxy HTTP → real PCP metrics → MCP response.

**Why this priority**: This is the highest-fidelity test possible. It replicates the exact runtime behaviour an AI assistant experiences. However, it requires real PCP infrastructure and is therefore slower and environment-dependent — making it P2, complementing rather than replacing the integration suite.

**Independent Test**: Can be fully tested when a real PCP-monitored host or a containerised PCP service is available. Gate with an environment variable so the suite is skipped (not failed) in environments without PCP.

**Acceptance Scenarios**:

1. **Given** a real pmproxy is available and `PMPROXY_URL` is set, **When** the E2E suite runs, **Then** pmmcp is launched as a subprocess and each tested tool returns a response containing real metric data from the live PCP host.
2. **Given** `PMPROXY_URL` is not set, **When** the E2E suite runs, **Then** all E2E tests are skipped with a clear message explaining the missing prerequisite — no tests fail.
3. **Given** `PMMCP_E2E` is not set to `1`, **When** the test suite runs, **Then** E2E tests are excluded even if `PMPROXY_URL` is set, allowing developers to run the live integration tests without triggering the heavier E2E suite.
4. **Given** pmmcp is launched as a subprocess pointing at a containerised PCP instance, **When** a tool requesting `kernel.all.load` data is called, **Then** the response contains at least one numeric data point — confirming the full stack is functional.

---

### User Story 3 - Continuous E2E Verification in GitHub Actions (Priority: P2)

A maintainer merges a pull request. The GitHub Actions CI pipeline automatically runs unit tests and integration tests (always) and E2E tests (when a containerised PCP service is available). If the E2E tests fail, the pipeline reports the failure before the merge reaches the main branch.

This closes the gap between "tests pass on my machine against a mock" and "it actually works against a real PCP installation." Regressions of the kind already seen — where response size limits required coarsening the auto-interval tiers — are caught in CI before they reach users.

**Why this priority**: Automating E2E in CI multiplies the value of the E2E suite. Without CI automation, the suite is only as reliable as individual developers remembering to run it.

**Independent Test**: Can be tested by inspecting the GitHub Actions workflow definition to confirm a containerised PCP service is declared and the E2E test step is present and gated correctly.

**Acceptance Scenarios**:

1. **Given** a pull request is opened, **When** the CI pipeline runs, **Then** unit tests and integration tests always run; E2E tests run against a containerised PCP service provided by the CI environment.
2. **Given** the CI pipeline runs E2E tests, **When** all tools return valid responses, **Then** the pipeline passes and the result is reported separately from unit and integration results.
3. **Given** a regression is introduced that breaks real pmproxy interaction, **When** the CI pipeline runs, **Then** the E2E suite fails and the pipeline blocks the merge.
4. **Given** the containerised PCP service fails to start, **When** the CI pipeline runs, **Then** the E2E tests are clearly marked as skipped (or failed with an infrastructure error), not silently passing.

---

### Edge Cases

- What happens when the mock pmproxy returns an unexpected HTTP status code during an integration test? Tests must fail with a clear diagnostic, not hang.
- What happens when the real PCP service in CI is healthy but a specific metric has no current data? Tests must only use metrics with guaranteed data in a containerised/VM environment (e.g. `kernel.all.load`, `mem.util.*`).
- What happens if the pmmcp subprocess exits unexpectedly during an E2E test? The test must report a meaningful error rather than blocking waiting for stdio output.
- What happens when both `PMPROXY_URL` and `PMMCP_E2E=1` are set in a developer's environment who only wants to run unit tests? The test marker system must allow them to exclude E2E explicitly via pytest options.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The integration test suite MUST exercise all nine MCP tools through the real MCP protocol dispatch path, not by calling implementation functions directly.
- **FR-002**: The integration test suite MUST use an in-process mock HTTP server to simulate pmproxy responses, with no dependency on any running service, container, or network resource.
- **FR-003**: The integration test suite MUST be executable in any standard CI environment (including GitHub Actions default runners) without Docker, without PCP, and without any prior setup beyond installing Python dependencies.
- **FR-004**: Integration tests MUST be identifiable and runnable separately from unit tests via a pytest marker, and MUST be included in the default test run.
- **FR-005**: The E2E test suite MUST launch pmmcp as a real subprocess and communicate with it exclusively via the MCP stdio protocol — the same transport used by AI assistants in production.
- **FR-006**: E2E tests MUST be skipped automatically when `PMPROXY_URL` is not set or when `PMMCP_E2E` is not set to `1`. Skipped tests MUST NOT be reported as failures.
- **FR-007**: E2E tests MUST only assert on metrics that are guaranteed to produce data in a containerised or virtual machine environment: `kernel.all.load`, `mem.util.*`, and `kernel.percpu.cpu.user` are approved; metrics requiring physical hardware inventory are not permitted.
- **FR-008**: The GitHub Actions CI workflow MUST be updated to provide a containerised PCP service (including pmcd and pmproxy) and run the E2E suite against it on every pull request and push to the main branch.
- **FR-009**: Both test suites MUST cover happy-path scenarios only in Phase 1. Error injection, context expiry simulation, and timeout fault scenarios are deferred to Phase 2.
- **FR-010**: The overall test coverage gate of ≥80% MUST continue to pass after both suites are added.
- **FR-011**: Integration and E2E tests MUST be housed in clearly separated directories (`tests/integration/` for integration tests and `tests/e2e/` for E2E tests) with no cross-contamination of responsibilities.

### Assumptions

- The `performancecopilot/pcp` Docker image is available on Docker Hub and provides a working pmcd and pmproxy accessible on port 44322.
- FastMCP's `Client` supports in-process server testing without requiring a network transport.
- The MCP Python SDK provides a stdio client capable of driving a subprocess server.
- `pytest-httpserver` or an equivalent in-process HTTP server library is available as a dev dependency.
- GitHub Actions default runners (ubuntu-latest) support Docker service containers.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All nine MCP tools are verified through the real MCP protocol dispatch path, with zero false failures on any standard CI runner that has no PCP installation.
- **SC-002**: A regression in any tool's MCP dispatch path is detectable by the integration suite within a CI run that completes in under 60 seconds for the integration tier alone.
- **SC-003**: A regression in any tool's behaviour against real PCP data is detectable by the E2E suite within a GitHub Actions pipeline run.
- **SC-004**: E2E tests skip gracefully (reported as skipped, not failed) on every developer machine and CI environment where real PCP is unavailable.
- **SC-005**: The overall test coverage gate of ≥80% is maintained after both suites land.
- **SC-006**: The CI pipeline clearly reports three distinct test tiers — unit, integration, and E2E — so failures are immediately attributable to the correct layer.
