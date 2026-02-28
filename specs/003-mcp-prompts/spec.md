# Feature Specification: MCP Prompts — Investigation Workflow Templates

**Feature Branch**: `003-mcp-prompts`
**Created**: 2026-02-27
**Status**: Draft
**Input**: User description: "MCP Prompts: Investigation Workflow Templates (4 prompts)"

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Guided Subsystem Investigation (Priority: P1)

An SRE suspects a performance problem on a host or fleet. They ask their AI assistant to investigate a specific subsystem (CPU, memory, disk, network, process, or general). The assistant follows a systematic expert investigation pattern: discover what metrics are available, assess the breadth of the problem, drill into anomalies, correlate related metrics, and produce a ranked findings report.

**Why this priority**: This is the most common SRE question ("Why is the system slow?") and covers the broadest set of investigation scenarios. It is the foundation that makes the tool useful daily.

**Independent Test**: Can be fully tested by requesting a subsystem investigation and verifying the assistant produces a structured findings report with ranked anomalies and supporting data — no other prompts required.

**Acceptance Scenarios**:

1. **Given** an MCP client connected to pmmcp, **When** a user requests `investigate_subsystem` with `subsystem=cpu` and an optional host, **Then** the assistant discovers available CPU metrics, identifies anomalous hosts, drills into details, and delivers a report ranked by severity with CPU values expressed as percentages.
2. **Given** an investigation for `subsystem=general`, **When** no host is specified, **Then** the assistant starts with load metrics, fans out to subsystems showing anomalies, and reports fleet-wide findings.
3. **Given** an investigation with a `symptom` argument, **When** the symptom is provided, **Then** the assistant uses it to prioritise which subsystems to examine first.
4. **Given** a subsystem investigation with an optional `timerange`, **When** the range is provided, **Then** the assistant restricts its analysis to that window.

---

### User Story 2 — Live Incident Triage (Priority: P2)

During an active incident, an SRE provides a natural-language symptom description (e.g., "API response times doubled"). The assistant interprets the symptom to identify likely subsystems, performs a rapid broad assessment, confirms scope (host-specific vs fleet-wide), identifies root cause via correlation, and delivers a concise findings report with recommended actions.

**Why this priority**: Incident triage is time-critical. Systematic, fast investigation reduces mean time to resolution and prevents tunnel-vision on the first anomaly found.

**Independent Test**: Can be tested by providing a symptom string and verifying the assistant identifies likely subsystems, reports anomalies with supporting metric evidence, and provides severity-ranked findings with recommended actions.

**Acceptance Scenarios**:

1. **Given** a symptom like "API response times doubled", **When** `incident_triage` is invoked, **Then** the assistant maps the symptom to likely subsystems (CPU, disk I/O, network), assesses anomalies, and returns findings ranked by severity of evidence found.
2. **Given** a symptom that conveys urgency (e.g., "production is completely down"), **When** triage runs, **Then** the investigation is driven by the data — the assistant follows anomalies wherever they lead regardless of how many subsystems are involved.
3. **Given** a known affected `host`, **When** triage is invoked with that host, **Then** the investigation focuses on that host first and broadens only if the root cause appears fleet-wide.
4. **Given** no identified anomalies in the first-guess subsystems, **When** triage continues, **Then** the assistant broadens to other subsystems rather than stopping.

---

### User Story 3 — Before/After Period Comparison (Priority: P2)

An SRE needs to understand what changed in system performance between two time windows — typically before and after a deployment, configuration change, or incident. They provide the two time ranges and optionally a description of what changed. The assistant performs a broad scan for changed metrics, identifies the most affected hosts, correlates related metrics, and produces a ranked list of changes with a root-cause hypothesis.

**Why this priority**: Post-change analysis is a daily SRE activity. Identifying regressions quickly reduces incident duration and prevents repeated issues.

**Independent Test**: Can be tested by providing two time windows with known differences and verifying the assistant returns metrics ranked by magnitude of change with correlation findings.

**Acceptance Scenarios**:

1. **Given** a baseline period and a comparison period, **When** `compare_periods` is invoked, **Then** the assistant scans for metrics that changed significantly between the two windows and reports them ranked by magnitude.
2. **Given** both time windows and an optional `context` description (e.g., "deployed v2.3.1"), **When** the comparison runs, **Then** the context is referenced in the report to help frame the findings.
3. **Given** a comparison scoped to a specific `subsystem`, **When** the scan runs, **Then** only metrics within that subsystem are scanned.
4. **Given** a comparison without a specified host, **When** the analysis runs, **Then** the report includes which hosts were most affected.

---

### User Story 4 — Fleet-Wide Health Check (Priority: P3)

An SRE wants a quick daily sweep of all monitored hosts and key subsystems to confirm everything is healthy or surface anything that needs attention. They invoke the health check, and the assistant enumerates all hosts, checks each configured subsystem, flags anomalies, and produces a concise summary table.

**Why this priority**: Enables proactive monitoring and early anomaly detection before problems become incidents. Valuable daily but less urgent than reactive investigation workflows.

**Independent Test**: Can be tested by invoking `fleet_health_check` and verifying the assistant returns a host-by-subsystem summary table with status indicators.

**Acceptance Scenarios**:

1. **Given** an MCP client and a connected fleet, **When** `fleet_health_check` is invoked with default settings, **Then** the assistant sweeps CPU, memory, disk, and network across all hosts and produces a summary table with per-host status.
2. **Given** a `detail_level=detailed` argument, **When** the check runs, **Then** the assistant additionally drills into anomalous hosts and provides correlated metric findings.
3. **Given** a custom `subsystems` argument (e.g., `cpu,memory`), **When** the check runs, **Then** only those subsystems are assessed.
4. **Given** a `timerange` argument, **When** the check runs, **Then** the assessment window is restricted accordingly.

---

### Edge Cases

- When a requested subsystem has no discoverable metrics on the connected fleet, the prompt instructs the agent to report this clearly and stop, suggesting the user verify that the subsystem is instrumented on the fleet.
- When a `timerange` falls outside available data retention, the prompt instructs the agent to report that no data exists for the requested window, suggest adjusting the timerange, and stop.
- When `compare_periods` baseline and comparison windows overlap, the prompt instructs the agent to detect this, report it as invalid input with an explanation of why overlapping windows produce unreliable results, and stop — asking the user to provide non-overlapping windows.
- When `fleet_health_check` finds no hosts registered, the prompt instructs the agent to report that no hosts were found, suggest verifying the monitoring configuration, and stop.
- When a natural-language symptom in `incident_triage` cannot be mapped to any known subsystem, the prompt instructs the agent to fall back to a broad general investigation across all subsystems, noting in the report that the symptom was ambiguous and a full sweep was performed.
- When prompts reference analysis tools that are not yet available on the connected server, the prompt instructs the agent to identify and report the specific missing tools, then abort with a clear message directing the user to deploy the required tools first.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST expose four named, parameterised prompt templates to any MCP-compatible client: `investigate_subsystem`, `compare_periods`, `fleet_health_check`, and `incident_triage`.
- **FR-002**: Each prompt MUST return a structured list of messages that seed an AI conversation with an expert investigation workflow.
- **FR-003**: `investigate_subsystem` MUST accept `subsystem` (required), and `host`, `timerange`, `symptom` (optional), supporting subsystem values: `cpu`, `memory`, `disk`, `network`, `process`, `general`.
- **FR-004**: `investigate_subsystem` MUST instruct the investigating agent to discover available metrics before assuming any metric names exist, using natural-language hints per subsystem rather than hardcoded metric paths.
- **FR-005**: `investigate_subsystem` MUST instruct the agent to present findings with CPU values as percentages, memory in GB, bandwidth in Mbps, and disk throughput in MB/s.
- **FR-006**: `compare_periods` MUST accept `baseline_start`, `baseline_end`, `comparison_start`, `comparison_end` (all required), and `host`, `subsystem`, `context` (optional).
- **FR-007**: `compare_periods` MUST instruct the agent to perform a broad scan for changed metrics, rank results by magnitude of change, and include a root-cause hypothesis.
- **FR-008**: `fleet_health_check` MUST accept `timerange`, `subsystems`, and `detail_level` (all optional), defaulting to a one-hour lookback, all four core subsystems, and summary-level output respectively.
- **FR-009**: `fleet_health_check` MUST instruct the agent to produce a concise host-by-subsystem summary table with status indicators.
- **FR-010**: `incident_triage` MUST accept `symptom` (required) and `host`, `timerange` (optional), defaulting to a one-hour lookback when not provided. Investigation depth is always data-driven; urgency is expressed through the `symptom` description, not a severity parameter.
- **FR-011**: `incident_triage` MUST include symptom-to-subsystem mapping guidance enabling the agent to interpret natural-language symptoms and prioritise investigation paths.
- **FR-012**: `incident_triage` MUST instruct the agent to confirm whether an issue is host-specific or fleet-wide before drilling into root causes.
- **FR-013**: All prompts MUST follow a discovery-first pattern: instruct the agent to enumerate available metrics before acting on any assumptions about metric names.
- **FR-017**: All prompts MUST instruct the agent to check for the availability of required analysis tools at the start of the workflow; if any required tool is absent, the agent MUST list the missing tools and abort with a message directing the user to deploy issue #8 tools before proceeding.
- **FR-018**: When metric discovery returns no results for a requested subsystem, the prompt MUST instruct the agent to report the gap clearly and stop, advising the user to verify that the subsystem is instrumented on the fleet. The agent MUST NOT silently fall back to a different subsystem.
- **FR-019**: When a `timerange` argument falls outside available data retention, all prompts MUST instruct the agent to report that no data exists for the requested window, suggest adjusting the timerange, and stop. The agent MUST NOT proceed with an empty or partial dataset without notifying the user.
- **FR-020**: `compare_periods` MUST instruct the agent to detect overlapping baseline and comparison windows before proceeding; if overlap is found, the agent MUST report it as invalid input, explain why overlapping windows produce unreliable results, and stop — requesting non-overlapping windows from the user.
- **FR-021**: `fleet_health_check` MUST instruct the agent to check that at least one host is registered before proceeding; if no hosts are found, the agent MUST report this and stop, suggesting the user verify their monitoring configuration.
- **FR-022**: `incident_triage` MUST instruct the agent to fall back to a broad general investigation across all subsystems when a symptom cannot be mapped to any known subsystem, noting in the report that the symptom was ambiguous and a full sweep was performed.
- **FR-014**: All prompts MUST use a layered investigation approach: start coarse (fleet-wide, broad subsystems) and drill into specifics only when anomalies are found.
- **FR-015**: Each agent definition file MUST be retired alongside its corresponding prompt — incrementally, one per prompt — with all investigation patterns and metric guidance migrated into the prompt before the file is deleted.
- **FR-016**: All four prompts MUST be registered with the MCP server and discoverable by MCP clients via standard prompt listing.

### Key Entities

- **Prompt Template**: A named, parameterised template that seeds an AI conversation. Has a name, argument schema (with required/optional fields and types), and returns a list of messages.
- **Prompt Argument**: A named input to a prompt. Has a name, type, required flag, and description.
- **Investigation Phase**: A logical step within a prompt workflow (e.g., discovery, assessment, drill-down, correlation, reporting). Each phase specifies investigative actions the agent must perform.
- **Subsystem**: A category of system resources under investigation: `cpu`, `memory`, `disk`, `network`, `process`, or `general`.
- **Agent Definition File** (retiring): Existing platform-specific subagent files whose investigation content is being migrated into MCP Prompts to become platform-agnostic.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All four prompts are discoverable by any standards-compliant MCP client immediately after connection — verified by prompt listing returning all four names with correct argument schemas.
- **SC-002**: Each prompt's argument schema is fully described and its response is well-formed — verified by contract tests covering argument names, types, and required flags AND confirming each prompt returns a non-empty, well-formed message list (without asserting exact text content).
- **SC-003**: An SRE can initiate a guided investigation through any MCP client using only the prompt's built-in guidance, without reading external documentation — verified by a new user successfully completing each workflow using only prompt-provided instructions.
- **SC-004**: All investigation patterns, metric hints, and presentation standards from the four retiring agent files are preserved in the new prompts — verified by a content migration audit confirming no guidance is lost.
- **SC-005**: All four agent definition files are absent from the codebase once their corresponding prompts are implemented — verified by file-system check.
- **SC-006**: The overall test suite continues to pass with coverage ≥ 80% after implementation — verified by CI pipeline.

## Clarifications

### Session 2026-02-27

- Q: When a prompt's required analysis tools are unavailable, what should the prompt instruct the agent to do? → A: Report which required tools are missing and abort the investigation with a clear message directing the user to deploy the tools first.
- Q: Should `incident_triage` include a `severity` parameter to control investigation depth? → A: Remove `severity`. Investigation breadth is always data-driven — a critical incident may show as a single metric or span many subsystems; a label should not constrain the investigation. Urgency is expressed naturally through the `symptom` description.
- Q: When no metrics are discoverable for a requested subsystem, what should the prompt instruct the agent to do? → A: Report "no metrics found for this subsystem" and stop, suggesting the user verify instrumentation on the fleet. Do not silently fall back to a broader investigation.
- Q: Should agent definition files be retired incrementally (one per prompt) or all at once at the end? → A: Incrementally — each agent file is retired alongside its corresponding prompt as a single coherent unit of work.
- Q: Should contract tests validate only the prompt argument schema, or also the returned message structure? → A: Both — verify argument schema AND that each prompt returns a non-empty, well-formed message list, without asserting exact text content.

### Session 2026-02-27 (Edge Cases)

- Q: When a `timerange` falls outside available data retention, what should the prompt instruct the agent to do? → A: Report no data exists for the requested window, suggest adjusting the timerange, and stop.
- Q: When `compare_periods` baseline and comparison windows overlap, what should the prompt instruct the agent to do? → A: Detect the overlap, report it as invalid input with an explanation, and stop — ask the user to provide non-overlapping windows.
- Q: When `fleet_health_check` finds no hosts registered, what should the prompt instruct the agent to do? → A: Report that no hosts were found, suggest verifying the monitoring configuration, and stop.
- Q: When a symptom in `incident_triage` cannot be mapped to any known subsystem, what should the agent do? → A: Fall back to a broad general investigation across all subsystems, noting in the report that the symptom was ambiguous.
- Q: Should the health check prompt use "cluster" or "fleet" as the collective noun for monitored hosts? → A: Rename to `fleet_health_check` and use "fleet" throughout. "cluster" conflicts with PCP's PMID structure terminology (domain.cluster.item). pmproxy has no canonical collective noun; "fleet" is standard SRE vocabulary with no PCP naming conflict.

## Assumptions

- The analysis tools introduced in issue #8 (`pcp_rank_hosts`, `pcp_detect_anomalies`, `pcp_scan_changes`, `pcp_correlate_metrics`) are available when these prompts are used; the prompts reference these tools by name in their workflow instructions.
- MCP clients are responsible for rendering the returned message lists; prompt correctness is measured by the quality and structure of the messages, not by client-side rendering.
- The four retiring agent files contain no runtime-referenced functionality — they are pure documentation consumed by Claude Code subagent workflows.
- Grafana integration hints within prompt templates are advisory and not hard dependencies.
- Time range arguments follow the existing pmmcp convention for time expressions (full unit forms, e.g., `-1hours`, `-7days`).
