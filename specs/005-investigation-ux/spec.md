# Feature Specification: Investigation UX Improvements

**Feature Branch**: `005-investigation-ux`
**Created**: 2026-03-04
**Status**: Draft
**Input**: User description: "Based on practice runs using pmmcp, improve: (1) session-init prompt/tool for common derived metrics, (2) incident_triage prompt workflow sequencing, (3) pcp_detect_anomalies as first-reach tool, (4) limit guidance in tool descriptions."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Session Initialisation with Common Derived Metrics (Priority: P1)

An SRE asks Claude to investigate a performance incident. Before any queries begin, Claude invokes a session-init prompt that pre-registers derived metrics for CPU utilisation %, disk utilisation %, and memory pressure. Those derived metrics are then immediately available for all subsequent tool calls in the session — without any manual `pcp_derive_metric` calls.

**Why this priority**: Without ready-made derived metrics, every investigation session either wastes early tool calls defining them or skips them entirely in favour of raw counters. Pre-registering them at session start removes that friction and ensures consistent, meaningful metrics across all investigations.

**Independent Test**: Can be fully tested by invoking the session-init prompt in a fresh session and verifying that the three derived metric names are registered and returnable in a subsequent `pcp_fetch_live` call — without any additional `pcp_derive_metric` calls.

**Acceptance Scenarios**:

1. **Given** Claude begins a new investigation session, **When** the session-init prompt is invoked, **Then** derived metrics for CPU utilisation %, disk utilisation %, and memory pressure are registered and available for immediate use.
2. **Given** the session-init prompt has been invoked, **When** Claude calls any subsequent metric query tool using one of the derived metric names, **Then** the query succeeds without a separate `pcp_derive_metric` step.
3. **Given** the session-init prompt is invoked, **When** it completes, **Then** it returns a summary listing each registered derived metric name with a brief description of what it measures.
4. **Given** the session-init prompt is invoked a second time in the same session, **When** it runs, **Then** it completes without error and does not create duplicate metric registrations.
5. **Given** a target host is missing an underlying counter needed for one derived metric, **When** session-init runs, **Then** it reports which metrics registered successfully and which failed, without aborting the session.

---

### User Story 2 - Guided Incident Triage Workflow (Priority: P2)

An SRE asks Claude to triage a production incident. Claude invokes the `incident_triage` prompt and follows a clearly prescribed four-step investigation sequence: anomaly detection → window comparison → scan changes → targeted drilldown. The prompt leaves no ambiguity about which tool to use at each step or what triggers the transition to the next step.

**Why this priority**: Without explicit sequencing, Claude may jump directly to raw data fetching (via `pcp_fetch_timeseries`) rather than starting with anomaly detection. This wastes tool calls, produces less structured findings, and makes triage results harder to explain.

**Independent Test**: Can be fully tested by invoking `incident_triage` and verifying that the returned prompt text names each of the four steps, specifies which tool to call first, and describes the criteria for advancing to the next step.

**Acceptance Scenarios**:

1. **Given** Claude invokes the `incident_triage` prompt, **When** it returns, **Then** the prompt text explicitly names all four investigation steps in the correct sequence.
2. **Given** the triage prompt is active, **When** Claude begins step one, **Then** it calls `pcp_detect_anomalies` before any other data-fetching tool.
3. **Given** step one anomaly detection results are available, **When** step two begins, **Then** Claude calls `pcp_compare_windows` to compare a good period against the anomalous window.
4. **Given** a comparison is complete, **When** step three begins, **Then** Claude calls `pcp_scan_changes` on the relevant metric namespace.
5. **Given** scan results identify specific changed metrics, **When** step four begins, **Then** Claude performs targeted drilldown only on those metrics using `pcp_fetch_timeseries`.

---

### User Story 3 - pcp_detect_anomalies as the Obvious First Tool (Priority: P3)

A Claude session begins investigating slow application response times. Without any explicit instruction, Claude reaches for `pcp_detect_anomalies` as the first investigative tool rather than `pcp_fetch_timeseries`. The tool's description makes this the natural default.

**Why this priority**: Tool selection is driven almost entirely by how tool descriptions are written. If `pcp_detect_anomalies` reads like a specialist option and `pcp_fetch_timeseries` reads like a general-purpose tool, Claude will default to the wrong one. The fix is purely in description copy.

**Independent Test**: Can be fully tested by reading the updated tool description and confirming it explicitly states `pcp_detect_anomalies` is the recommended starting point, and that `pcp_fetch_timeseries` is for drill-down after anomalies are identified.

**Acceptance Scenarios**:

1. **Given** the `pcp_detect_anomalies` tool description is updated, **When** read by Claude, **Then** it explicitly states this tool should be used first at the start of any investigation.
2. **Given** the `pcp_fetch_timeseries` tool description is read, **When** compared to `pcp_detect_anomalies`, **Then** it describes `pcp_fetch_timeseries` as a follow-up drill-down tool, not a starting point.
3. **Given** the tool descriptions are updated, **When** Claude faces an open-ended performance question with no other context, **Then** it chooses `pcp_detect_anomalies` as its first call.

---

### User Story 4 - Limit Parameter Guidance in Tool Descriptions (Priority: P4)

An SRE asks Claude to explore what metrics are available for a given subsystem. Claude selects an appropriate `limit` value (e.g., 50) for exploration rather than requesting a large dataset. When Claude later performs a full dataset analysis, it increases the limit intentionally and explains why. Tool descriptions guide this behaviour without human intervention.

**Why this priority**: Unguided limit selection leads to either over-fetching (large limits wasting tokens and time) or under-fetching (small limits that miss relevant data during analysis). Clear guidance text shapes the default behaviour.

**Independent Test**: Can be fully tested by reading the updated tool descriptions for tools that accept a `limit` parameter and verifying they include explicit guidance distinguishing exploration from full-dataset use cases with a concrete suggested value.

**Acceptance Scenarios**:

1. **Given** a tool description is updated, **When** it includes a `limit` parameter, **Then** the description explicitly states a recommended exploration value and explains when to increase it.
2. **Given** Claude is performing broad metric discovery, **When** it chooses a limit value, **Then** it uses the exploration-tier value unless it has a specific reason to use more.
3. **Given** Claude increases the limit beyond the exploration default, **When** it does so, **Then** it states its reason for doing so.

---

### Edge Cases

- What happens when the session-init prompt is invoked multiple times in the same session? Derived metric re-registration must be idempotent — no errors, no duplicates.
- What if `pcp_derive_metric` fails for one of the standard metrics (e.g., missing underlying counter on the target host)? The session-init prompt must report which metrics succeeded and which failed, without halting the session.
- What if the investigator invokes `incident_triage` mid-investigation rather than at the start? The prompt should still be actionable — it describes a process, not a gate.
- What if a tool accepts `limit` but has a context where any limit is inappropriate (e.g., internally bounded)? Only tools where user-supplied limit meaningfully affects result volume should carry the guidance.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a session-initialisation prompt that, when invoked, registers derived metrics for CPU utilisation percentage, disk utilisation percentage, and memory pressure.
- **FR-002**: The session-init prompt MUST return a human-readable summary of each registered derived metric name and what it measures.
- **FR-003**: Derived metric registration is idempotent because `pcp_derive_metric` silently overwrites an existing registration with the same name. The session-init prompt MAY re-register unconditionally — no guard logic required.
- **FR-004**: After registering each derived metric, the session-init prompt MUST instruct Claude to call `pcp_fetch_live` for each derived metric name to verify availability. Since registration always succeeds, failure surfaces only at fetch time. The prompt MUST instruct Claude to report which metrics returned data and which failed, without aborting the session.
- **FR-005**: The `incident_triage` prompt MUST be a full rewrite of `triage.py`, prescribing a four-step investigation sequence as its primary spine — in this order: (1) anomaly detection via `pcp_detect_anomalies`, (2) window comparison via `pcp_compare_windows`, (3) change scanning via `pcp_scan_changes`, (4) targeted drilldown via `pcp_fetch_timeseries`. The existing triage prompt content is replaced entirely.
- **FR-006**: Each step in the `incident_triage` sequence MUST name the specific tool to invoke and describe advancement criteria in qualitative terms (e.g. "if anomalies are found, proceed to comparison") — not hardcoded numeric thresholds. Claude applies contextual judgment.
- **FR-007**: The `pcp_detect_anomalies` tool description MUST explicitly state that it is the recommended first tool at the start of any investigation.
- **FR-008**: The `pcp_fetch_timeseries` tool description MUST characterise it as a drill-down tool for use after anomalies are identified, not a general starting point.
- **FR-009**: All tools that accept a user-supplied `limit` parameter MUST include guidance in their description distinguishing the appropriate value for exploration (with a concrete suggested default of 50) from the value appropriate for full dataset analysis.

### Key Entities

- **Session-init prompt**: A new MCP prompt that sequences `pcp_derive_metric` calls to register standard derived metrics at investigation start.
- **Derived metric**: A computed metric built from existing PCP counters using the following canonical expressions:
  - `derived.cpu.utilisation` = `100 - rate(kernel.all.cpu.idle) / hinv.ncpu / 10` (complement-of-idle; captures user+sys+nice+wait+steal on any OS)
  - `derived.disk.utilisation` = `rate(disk.all.avactive) / 10` (aggregate disk busy %)
  - `derived.mem.utilisation` = `100 * mem.util.used / mem.physmem` (used memory as % of physical)
- **Tool description**: The natural-language text that describes a tool's purpose and usage, consumed by Claude when selecting which tool to call.
- **Investigation workflow**: The ordered sequence of tool calls prescribed by the `incident_triage` prompt.

## Clarifications

### Session 2026-03-04

- Q: What PCP expressions should be used for the three derived metrics? → A: `derived.cpu.utilisation = 100 - rate(kernel.all.cpu.idle) / hinv.ncpu / 10`; `derived.disk.utilisation = rate(disk.all.avactive) / 10`; `derived.mem.utilisation = 100 * mem.util.used / mem.physmem`. Idle-complement chosen for CPU to capture all non-idle states (user/sys/nice/wait/steal) cross-platform.
- Q: Does pcp_derive_metric silently overwrite on duplicate registration, or error? → A: Silently overwrites — idempotency is free, the session-init prompt needs no guard logic for duplicate registrations.
- Q: Should incident_triage step transitions use concrete thresholds or qualitative guidance? → A: Qualitative — e.g. "if anomalies are found, advance to comparison." Claude applies contextual judgment; hardcoded z-score thresholds in prompt copy are fragile and create false precision.
- Q: Is the existing incident_triage prompt being wholly rewritten or incrementally amended? → A: Full rewrite — replace triage.py content with the explicit 4-step sequence as its spine. Patching around an incorrectly-sequenced prompt leaves contradictory guidance.
- Q: Should session-init instruct Claude to verify each derived metric via a fetch after registration? → A: Yes — prompt instructs Claude to call `pcp_fetch_live` for each derived metric name after registering and report any that fail. This is the only way to honour FR-004 since registration itself always succeeds.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After invoking the session-init prompt, all three standard derived metrics (CPU util%, disk util%, memory pressure) are available for immediate querying in the same session — verified by a subsequent successful fetch using each derived metric name without any additional `pcp_derive_metric` calls.
- **SC-002**: The `incident_triage` prompt text, when parsed, contains all four investigation step names in the correct sequence, each referencing the appropriate tool by name.
- **SC-003**: In any new investigation session starting from the `incident_triage` prompt, `pcp_detect_anomalies` is called before `pcp_fetch_timeseries` with no human guidance required.
- **SC-004**: All tools with a user-supplied `limit` parameter have updated descriptions that include an explicit exploration-tier default value (50) and guidance on when to increase it.
- **SC-005**: Invoking the session-init prompt twice in a row produces the same successful outcome as invoking it once — no error, no duplicate entries.

## Assumptions

- The PCP instances targeted during a session expose the standard kernel and disk metrics needed to compute the three derived metrics (`kernel.all.cpu.idle`, `hinv.ncpu`, `disk.all.avactive`, `mem.util.used`, `mem.physmem`). Hosts missing these counters will experience partial session-init success, which is acceptable behaviour.
- `derived.mem.utilisation` is defined as `100 * mem.util.used / mem.physmem` — used memory as a percentage of total physical memory.
- `derived.disk.utilisation` uses aggregate busy time (`disk.all.avactive`) across all devices, not per-partition capacity. Per-disk breakdown remains available via existing tools.
- Tool description updates are text-only changes — no schema changes, no new tool registrations, and no breaking changes to existing tool signatures.
- The exploration-tier `limit` default suggested in descriptions is 50. This matches existing tool documentation conventions observed in the codebase.
- The session-init prompt is a new MCP prompt (not a tool) — it returns instructional text that Claude acts upon, rather than directly executing side effects itself.
