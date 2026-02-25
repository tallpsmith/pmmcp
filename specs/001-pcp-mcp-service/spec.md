# Feature Specification: PCP MCP Service (pmmcp)

**Feature Branch**: `001-pcp-mcp-service`
**Created**: 2026-02-20
**Status**: Completed
**Input**: User description: "Create a Claude Code-compatible MCP service and companion subagents that allow Claude to interact with PCP through its pmproxy REST API interfaces and allow AI-analysis of performance problems of running systems."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Interactive Performance Investigation (Priority: P1)

A systems engineer notices degraded application behaviour (elevated error rates, slow response times, or unusual resource consumption). They open Claude Code and describe the problem in natural language. The system retrieves relevant performance data from one or more monitored hosts, analyses trends and anomalies, and presents a human-readable explanation of likely causes, correlated changes, and recommended next steps.

**Why this priority**: This is the core value proposition — turning raw performance telemetry into actionable human insight via natural language. Without this, the product has no reason to exist.

**Independent Test**: Can be fully tested by connecting to a PCP-monitored host with known metric data, asking a natural language question about performance, and verifying the system returns a relevant, data-backed analysis.

**Acceptance Scenarios**:

1. **Given** a PCP-monitored host with elevated CPU utilisation over the last 2 hours, **When** a user asks "Why is the system slow right now?", **Then** the system retrieves CPU, memory, I/O, and network metrics for the relevant time window, identifies the anomalous metric(s), and returns a natural language summary explaining the likely cause.
2. **Given** multiple monitored hosts in a cluster, **When** a user asks "Which host is having the most trouble?", **Then** the system queries metrics across all hosts, ranks them by anomaly severity, and highlights the most problematic host(s) with supporting data.
3. **Given** a PCP-monitored host with stable recent history, **When** a user asks about problems that do not exist, **Then** the system reports that no significant anomalies were detected and summarises the current healthy state.

---

### User Story 2 - Metric Discovery and Exploration (Priority: P2)

A user wants to understand what performance data is available across their monitored infrastructure. They ask the system to list available hosts, metrics, or metric categories. The system queries PCP, returns structured results, and can explain what individual metrics represent and why they matter.

**Why this priority**: Users must be able to discover what data exists before they can ask meaningful analytical questions. This is a prerequisite for effective use of P1 but delivers standalone value as a PCP knowledge assistant.

**Independent Test**: Can be fully tested by connecting to a PCP instance and asking "What metrics are available on this host?" — the system returns a categorised list with descriptions.

**Acceptance Scenarios**:

1. **Given** a PCP-monitored host, **When** a user asks "What metrics are being collected?", **Then** the system returns a categorised summary of available metric namespaces with human-readable descriptions.
2. **Given** a multi-host PCP deployment, **When** a user asks "Which hosts are being monitored?", **Then** the system returns a list of all reachable hosts with their status.
3. **Given** a specific metric name, **When** a user asks "What does kernel.percpu.cpu.user mean?", **Then** the system provides a clear explanation of the metric, its units, its semantics, and typical use cases.

---

### User Story 3 - Comparative Time-Period Analysis (Priority: P2)

A user knows that the system was "fine last week" but "bad today". They ask the system to compare performance characteristics between a known-good period and a known-bad period to identify statistically significant changes. The system retrieves data for both windows, performs comparison, and highlights the most significant deviations.

**Why this priority**: This directly addresses the "pmdiff but smarter" use case described in the feature vision. It builds on P1 capabilities but adds temporal comparison, which is the most common real-world troubleshooting workflow.

**Independent Test**: Can be fully tested by loading known-different metric datasets for two time periods, asking for a comparison, and verifying the system correctly identifies the metrics that changed most significantly.

**Acceptance Scenarios**:

1. **Given** a host with distinctly different performance profiles between two time periods, **When** a user says "Compare this week to last week", **Then** the system retrieves metrics for both periods, calculates statistical differences, and reports the top changes ranked by significance.
2. **Given** two time periods with identical performance, **When** a user requests a comparison, **Then** the system reports no significant differences found.

---

### User Story 4 - Periodic Summary Reports (Priority: P3)

A user requests a summary report covering a defined time period (e.g., "last month", "past 7 days") across their services. The system generates a structured report showing key performance indicators, trend direction, and highlights services that have improved or degraded significantly.

**Why this priority**: Reports are high-value but less urgent than interactive investigation. They require the same underlying data retrieval and analysis capabilities as P1-P2 but packaged as a structured output rather than conversational response.

**Independent Test**: Can be fully tested by requesting a summary over a known data window and verifying the report contains correct KPIs, trend indicators, and degradation/improvement flags for each service.

**Acceptance Scenarios**:

1. **Given** a cluster of monitored hosts over the past 30 days, **When** a user requests "Give me a monthly summary of all services", **Then** the system produces a structured report showing p95 response time, error rate, and throughput for each service, with trend indicators (improving/stable/degrading).
2. **Given** a specific service with a sudden degradation mid-period, **When** the report is generated, **Then** the degradation is flagged and the approximate onset time is noted.

---

### User Story 5 - Automated Proactive Monitoring (Priority: DEFERRED)

> **DEFERRED to a future iteration.** This story requires persistent state, background scheduling, and a notification delivery mechanism — fundamentally different infrastructure from the interactive analysis tools in US1-US4. It will be designed and built as a separate architectural phase after the core interactive capabilities are proven.

---

### Edge Cases

- What happens when the pmproxy service is unreachable or returns errors?
- How does the system handle metrics that have no recent data (stale or discontinued collectors)?
- What happens when a user references a time period for which no archived data exists?
- How does the system behave when the monitored host set changes between comparison periods?
- What happens when a metric query returns an extremely large result set (thousands of metrics across dozens of hosts)? → Tools enforce pagination with default limits; subagents use coarse-to-fine sampling strategy to manage data volume intelligently.
- How does the system handle ambiguous natural language queries where the intent is unclear?
- What happens when metric names conflict or overlap across different host configurations?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST expose a set of MCP-compatible tools that allow an AI assistant to query performance data through the pmproxy service. The initial build MUST support stdio transport (subprocess launched by Claude Code). The architecture MUST cleanly separate tool handler logic from transport so that Streamable HTTP transport can be added in a future iteration without rewriting tool implementations.
- **FR-002**: The system MUST support querying live (real-time) metric values from one or more monitored hosts.
- **FR-003**: The system MUST support querying historical (time-series) metric values over user-specified time windows.
- **FR-004**: The system MUST support metric discovery — listing available hosts, metric namespaces, and individual metric metadata (type, units, semantics, help text).
- **FR-005**: The system MUST support full-text search across metric names, descriptions, and help text to allow AI-driven metric identification.
- **FR-006**: The system MUST support multi-host queries, allowing data retrieval and comparison across all hosts visible to a pmproxy instance.
- **FR-007**: The system MUST return data in structured formats that enable the AI agent to perform statistical analysis (averages, percentiles, standard deviations, trend detection). MCP tools MUST enforce default result size limits and support pagination so the AI agent can request additional data incrementally.
- **FR-008**: The system MUST provide companion subagent definitions that encode domain knowledge about performance metrics, analysis methodology, and troubleshooting workflows. Subagent definitions MUST encode a hierarchical sampling strategy: query broad time ranges at coarse intervals first (e.g., 5-minute or hourly samples for days/weeks of data), identify patterns of interest, then drill down into narrower time blocks at finer granularity (e.g., 15-second samples) for detailed investigation.
- **FR-009**: The system MUST handle pmproxy connection failures gracefully, returning informative error descriptions rather than raw technical errors.
- **FR-010**: The system MUST support configurable pmproxy endpoint connection details (host, port, protocol). Authentication is out of scope for the initial build but the configuration design MUST accommodate future addition of optional credentials without breaking changes.
- **FR-011**: The system MUST support time-series comparison between two user-specified time windows for the same set of metrics.
- **FR-012**: The system MUST support derived metric creation to allow the AI agent to compute custom aggregations or ratios on-the-fly.

### Key Entities

- **Host**: A monitored machine running performance collectors, identified by hostname; exposes a set of performance metrics.
- **Metric**: A named performance measurement (e.g., `kernel.percpu.cpu.user`), with associated type, units, semantics, instance domain, and help text.
- **Instance Domain**: A set of related instances within a metric (e.g., individual CPUs, disk devices, network interfaces).
- **Time Window**: A bounded time range defined by start time, end time, and optional sampling interval, used to scope metric queries.
- **Metric Value**: A timestamped data point for a specific metric and instance, returned as part of a time-series query.
- **Subagent Definition**: A pre-built agent prompt template that encodes performance domain knowledge and analysis methodology for specific use cases (investigation, comparison, reporting, monitoring).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can retrieve current performance data for a specific host within 5 seconds of making a natural language request.
- **SC-002**: Users can retrieve and receive analysis of historical performance data over a 7-day window within 15 seconds.
- **SC-003**: The system correctly identifies the top 3 most anomalous metrics in a degraded-performance scenario at least 80% of the time when validated against expert analysis.
- **SC-004**: Users can discover available hosts and metrics within 10 seconds, with results grouped into understandable categories.
- **SC-005**: Time-period comparison reports correctly identify statistically significant metric changes (> 2 standard deviations) with at least 90% precision.
- **SC-006**: Users with no prior PCP knowledge can ask a performance question and receive a useful, actionable answer without needing to know metric names or query syntax.
- **SC-007**: The system supports monitoring at least 50 hosts simultaneously through a single pmproxy instance without degradation in query response times.
- **SC-009**: All MCP tools are discoverable and usable from Claude Code without additional configuration beyond providing the pmproxy endpoint URL.

## Clarifications

### Session 2026-02-20

- Q: Should automated proactive monitoring (US5) be included in the initial build or deferred? → A: Defer US5 to a future iteration; focus initial build on US1-US4 (interactive analysis tools). US5 is a separate architectural phase to be added on subsequently.
- Q: Should the system support pmproxy authentication credentials? → A: Initial build assumes no authentication (unauthenticated pmproxy access). Optional authentication (username/password) is planned for a future iteration.
- Q: Should the system support multiple pmproxy endpoints? → A: Single pmproxy endpoint configured once; multi-host queries handled by pmproxy's built-in aggregation. Multi-pmproxy support deferred to a future iteration.
- Q: How should the system handle large metric result sets? → A: MCP tools enforce default result limits with pagination; the AI agent can request subsequent pages. Additionally, subagent definitions MUST encode a hierarchical sampling strategy: use coarse-grained intervals (e.g., 5-minute or hourly) for broad time ranges (days/weeks), identify interesting patterns at that level, then drill down into specific time blocks at finer granularity (e.g., 15-second) for detailed investigation.
- Q: Which MCP transport mode should the system use? → A: stdio transport for the initial build (launched as subprocess by Claude Code, connecting to a remote pmproxy). Streamable HTTP transport to be added in a future phase to support centralised deployment of pmmcp alongside pmproxy, enabling multi-user access. Architecture MUST cleanly separate tool handlers from transport layer to support both modes without duplication.

## Assumptions

- PCP and pmproxy are already installed, configured, and running on the target infrastructure. This product does not manage PCP installation or configuration.
- The pmproxy instance has been configured with a key-value store backend to enable time-series and multi-host queries. Without this, only live single-host queries are available.
- Users interact with this system through Claude Code (CLI) or a compatible MCP client. The system does not provide its own user interface.
- The pmproxy REST API is accessible over the network from where the MCP service runs without authentication. Network connectivity and firewall configuration are the user's responsibility.
- Authentication support for pmproxy (HTTP Basic Auth, proxy tokens) is deferred to a future iteration.
- The system connects to a single pmproxy instance. Multi-pmproxy endpoint support (e.g., per-data-centre routing) is deferred to a future iteration.
- PCP metric semantics (names, types, units) follow standard PCP conventions. Custom metrics from third-party PMDAs are supported but may have limited AI-interpretable metadata.
- The companion subagent definitions are designed for Claude but the MCP tools themselves are model-agnostic and follow the MCP specification.
- The initial deployment model is local (user runs pmmcp as a subprocess via stdio, connecting to a remote pmproxy). A future iteration will add Streamable HTTP transport to support centralised deployment of pmmcp alongside pmproxy for multi-user access.
