# Feature Specification: Grafana & mcp-grafana Compose Integration

**Feature Branch**: `012-grafana-compose`
**Created**: 2026-03-10
**Status**: Draft
**Input**: User description: "Issue #10 - we'll definitely need to add in Grafana and mcp-grafana into our docker-compose setup."
**Related**: [Issue #10 — External Integration Contracts (Grafana MCP, reporting strategy)](https://github.com/tallpsmith/pmmcp/issues/10)

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Grafana with PCP Datasource Available Out of the Box (Priority: P1)

A developer runs `podman compose up -d` and gets a fully wired Grafana instance with the PCP datasource plugin pre-configured and pointing at the same pmproxy that pmmcp uses. No manual Grafana setup required — the datasource is provisioned automatically.

**Why this priority**: Without a pre-configured Grafana instance, nothing in Issue #10's prompt-driven visualisation workflow can function. This is the foundation.

**Independent Test**: After `podman compose up -d`, navigate to Grafana's datasource API and confirm the PCP datasource exists, is healthy, and targets the correct pmproxy URL.

**Acceptance Scenarios**:

1. **Given** the compose stack is running, **When** a user opens Grafana in a browser (`http://localhost:3000`), **Then** Grafana is accessible without additional setup and the PCP datasource is listed and healthy.
2. **Given** the compose stack is running, **When** a user queries Grafana's datasource health endpoint for the PCP datasource, **Then** it reports success (pmproxy is reachable).
3. **Given** the compose stack is running, **When** a user explores metrics via the PCP datasource in Grafana, **Then** the same metrics visible through pmmcp's tools are available (they share the same pmproxy backend).

---

### User Story 2 — mcp-grafana Available as a Compose Service (Priority: P2)

A developer can start mcp-grafana alongside pmmcp so that Claude (or integration tests) can orchestrate between both MCP servers. mcp-grafana connects to the same Grafana instance from Story 1.

**Why this priority**: mcp-grafana is the mechanism Claude uses to create dashboards. Without it in the compose stack, the prompt-driven visualisation from Issue #10 cannot be tested end-to-end locally.

**Independent Test**: After `podman compose up -d`, confirm mcp-grafana is running and can communicate with the Grafana instance (e.g., list datasources via mcp-grafana's tools).

**Acceptance Scenarios**:

1. **Given** the compose stack is running, **When** a client connects to the mcp-grafana service, **Then** mcp-grafana responds and can list the Grafana datasources (including the PCP datasource).
2. **Given** the compose stack is running, **When** mcp-grafana is used to create a dashboard, **Then** the dashboard appears in Grafana and can query PCP metrics via the provisioned datasource.

---

### User Story 3 — CI Parity for Grafana Services (Priority: P3)

The GitHub Actions CI workflow is updated so that the Grafana + mcp-grafana services are available during E2E tests, maintaining the local/CI parity rule documented in CLAUDE.md.

**Why this priority**: Grafana integration tests that pass locally but fail in CI are worse than no tests. Parity is a project convention and must be maintained, but it can follow the initial compose work.

**Independent Test**: CI E2E job starts the Grafana services and a smoke test confirms the PCP datasource is healthy before Grafana-specific E2E tests run.

**Acceptance Scenarios**:

1. **Given** a CI run triggers the E2E job, **When** the Grafana-related services start, **Then** the PCP datasource health check passes before E2E tests execute.
2. **Given** the compose file adds new services, **When** a developer compares `docker-compose.yml` with the CI workflow, **Then** the same service topology is reflected in both.

---

### Edge Cases

- What happens when Grafana starts before pmproxy is ready? The PCP datasource health check should fail initially and recover once pmproxy is available — Grafana retries datasource connections.
- What happens when the PCP datasource plugin is not available in the Grafana image? The compose configuration must ensure the plugin is installed (via `GF_INSTALL_PLUGINS` environment variable or a custom image).
- What happens when mcp-grafana cannot reach Grafana? mcp-grafana should report connection errors clearly; compose `depends_on` with a Grafana healthcheck ensures ordering.
- What happens when `podman compose down --volumes` is run? All Grafana state (dashboards, preferences) is ephemeral and destroyed — this is expected for a dev/test stack.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The compose stack MUST include a Grafana service accessible on a well-known port (`3000`).
- **FR-002**: The Grafana service MUST have the `performancecopilot-pcp-app` datasource plugin installed and enabled.
- **FR-003**: The PCP datasource MUST be auto-provisioned (via Grafana provisioning files) pointing at the compose stack's pmproxy instance (`http://pcp:44322`).
- **FR-004**: The Grafana service MUST have a healthcheck that confirms Grafana is ready to serve requests.
- **FR-005**: The Grafana service MUST depend on the `pcp` service so the datasource has a backend to connect to.
- **FR-006**: The compose stack MUST include an mcp-grafana service configured to connect to the Grafana instance.
- **FR-007**: The mcp-grafana service MUST depend on the Grafana service being healthy before starting.
- **FR-008**: Grafana MUST use anonymous authentication with admin privileges for the dev/test stack (no login required).
- **FR-009**: The PCP datasource provisioning MUST use the same pmproxy URL that pmmcp is configured with, ensuring a single source of truth.
- **FR-010**: The CI workflow MUST be updated to include Grafana and mcp-grafana services matching the compose topology.

### Key Entities

- **Grafana Service**: The visualisation platform, pre-configured with the PCP datasource plugin and provisioned datasource. Ephemeral state (no persistent volumes for dev/test).
- **PCP Datasource**: A Grafana datasource of type `performancecopilot-pcp-app` that connects to pmproxy, auto-provisioned via Grafana's file-based provisioning.
- **mcp-grafana Service**: The Grafana MCP server ([grafana/mcp-grafana](https://github.com/grafana/mcp-grafana)) providing Claude with tools for dashboard CRUD, queries, annotations, and deeplinks.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A fresh `podman compose up -d` results in all services healthy within 90 seconds, including Grafana with a working PCP datasource.
- **SC-002**: The PCP datasource in Grafana can query at least one metric that is also queryable via pmmcp tools (proving shared backend).
- **SC-003**: mcp-grafana can list datasources and create a test dashboard programmatically after compose stack startup.
- **SC-004**: CI E2E tests that exercise Grafana services pass with the same success rate as local runs.
- **SC-005**: No existing E2E tests break as a result of adding the new services.

## Assumptions

- The `performancecopilot-pcp-app` Grafana plugin is available for installation via `GF_INSTALL_PLUGINS` or is bundled in a suitable Grafana image.
- The `grafana/mcp-grafana` project publishes a container image (or can be built from source) suitable for inclusion in the compose stack.
- Anonymous admin access is acceptable for a local dev/test compose stack (not a production configuration).
- Grafana state is ephemeral — no persistent volumes needed; dashboards are recreated as needed.
- The mcp-grafana service uses SSE or stdio transport; compose configuration will expose the appropriate port/protocol.
