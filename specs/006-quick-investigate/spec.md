# Feature Specification: Low-Friction Open-Ended Investigation Entry Point

**Feature Branch**: `006-quick-investigate`
**Created**: 2026-03-05
**Status**: Draft
**Input**: User description: "https://github.com/tallpsmith/pmmcp/issues/19"
**Issue**: [#19 — agent bypasses summary tools and reaches for raw pcp_fetch_timeseries](https://github.com/tallpsmith/pmmcp/issues/19)

## Background

When an agent receives open-ended investigation questions ("anything interesting at 2pm?"), it currently bypasses purpose-built summary and anomaly detection tools in favour of raw time-series fetches that produce 15k+ token data dumps. Two causes are identified: (1) a known connection bug (#18) causes summary tools to fail, forcing fallback; (2) even without failures, the summary tools require up-front commitment to specific metrics and exact time windows — a mismatch for *discovery mode* where the agent doesn't yet know what's interesting.

This feature adds a low-friction investigation entry point that wraps anomaly detection with smart defaults, and strengthens tool descriptions and prompt guidance so the agent naturally reaches for summary tools first.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Quick investigate with just a time of interest (Priority: P1)

An operator asks "was anything unusual happening around 2pm yesterday?" The agent calls a single tool with only a timestamp, receiving a ranked list of anomalous metrics with a brief explanation — without needing to know which metrics to examine or what time windows to baseline against.

**Why this priority**: Directly solves the core UX problem. Reduces parameter burden from 6+ required fields to 1 required field, making the summary path the *easiest* path.

**Independent Test**: Can be fully tested by calling the new tool with only a `time_of_interest` parameter and verifying that a meaningful anomaly summary is returned without additional input.

**Acceptance Scenarios**:

1. **Given** a running system with recent metrics, **When** the tool is called with only `time_of_interest="2025-01-15 14:00"`, **Then** it returns a ranked list of metrics with anomaly scores and human-readable summaries within a reasonable token budget.
2. **Given** a time with no unusual activity, **When** the tool is called with that timestamp, **Then** it returns a clear "nothing anomalous detected" response rather than an empty result or error.
3. **Given** a time outside the available data range, **When** the tool is called, **Then** it returns a clear explanation of the available data range rather than crashing or returning misleading results.

---

### User Story 2 — Agent naturally reaches for summary tools before raw fetches (Priority: P2)

When an AI agent receives an open-ended investigation question, its tool selection logic steers it to the new quick-investigate tool (or existing anomaly detection tools) *before* it reaches for raw time-series fetches. The agent's first tool call in a discovery session should be a summary tool, not `pcp_fetch_timeseries`.

**Why this priority**: Behaviour change is only valuable if the agent actually uses it. Tool descriptions and prompt guidance must make the summary path obviously correct.

**Independent Test**: Can be tested by presenting an agent with open-ended investigation prompts and observing that the first tool called is a summary tool, not `pcp_fetch_timeseries`.

**Acceptance Scenarios**:

1. **Given** an agent with access to all tools, **When** asked "anything interesting happening this morning?", **Then** the agent's first tool call is a summary or investigation tool, not `pcp_fetch_timeseries`.
2. **Given** tool descriptions for both the new entry point and `pcp_fetch_timeseries`, **When** an agent reads them, **Then** the new tool's description clearly signals it is the correct starting point for discovery, and `pcp_fetch_timeseries` signals it is for targeted retrieval after a metric of interest has been identified.

---

### User Story 3 — Customise investigation scope when needed (Priority: P3)

A more experienced operator wants to investigate a specific subsystem (e.g., "disk I/O") around a known incident time with a custom baseline window. They can pass optional parameters to narrow or widen the scope without losing the smart defaults.

**Why this priority**: Covers the power-user path; the core value is delivered by P1 and P2.

**Independent Test**: Can be tested by calling the tool with optional parameters (`subsystem`, `lookback`, `baseline_days`) and verifying results are scoped accordingly.

**Acceptance Scenarios**:

1. **Given** a `subsystem="disk"` parameter, **When** the tool runs, **Then** results are limited to disk-related metrics rather than all available metrics.
2. **Given** `lookback="30minutes"` and `baseline_days=14`, **When** the tool runs, **Then** the comparison window and baseline period reflect those values.

---

### Edge Cases

- **No metrics for requested time**: Return a clear message explaining data is unavailable for that period — no error, no empty result.
- **Far-past time with no baseline**: Return available results with a warning that baseline comparison was limited or unavailable.
- **Underlying tool error (e.g., `pcp_detect_anomalies` failure, pmproxy timeout)**: Fail fast — propagate the error with a clear message and suggest checking pmproxy health. No silent fallback.
- **Too many anomalous metrics (system-wide outage)**: Cap at FR-003 limit (50 results), ranked by severity, with a note that results were truncated.
- **Future `time_of_interest`**: Reject with a clear validation error — the tool only analyses historical data.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a tool named `pcp_quick_investigate` that accepts a single required parameter (`time_of_interest`) and returns a ranked anomaly summary without requiring the caller to specify metrics, baseline windows, or comparison windows.
- **FR-002**: The tool MUST apply sensible defaults: a lookback window of 2 hours centred on `time_of_interest`, and a baseline derived from the 7 days prior to the event window.
- **FR-003**: The tool MUST cap its output to a bounded result set (at most 50 metric results) to prevent the 15k+ token dumps the current pattern produces.
- **FR-004**: The tool MUST accept optional parameters to narrow scope: a subsystem/category filter, a custom lookback duration, and a custom baseline length in days.
- **FR-005a**: The tool MUST dynamically discover available metrics by calling `pcp_discover_metrics` (not a hardcoded list), then feed the discovered metrics into anomaly detection. When a `subsystem` filter is provided, discovery is scoped to that category.
- **FR-005**: Tool descriptions for `pcp_detect_anomalies`, `pcp_compare_windows`, and `pcp_scan_changes` MUST be updated to clarify their role as *confirmation* tools, not *discovery* tools.
- **FR-006**: The `pcp_quick_investigate` tool description MUST explicitly position it as the correct first step for open-ended or discovery-mode investigation questions.
- **FR-007**: The `pcp_fetch_timeseries` tool description MUST be updated to clarify it is for targeted retrieval of a *known* metric of interest, not for exploratory investigation.
- **FR-008**: The `investigate_subsystem` MCP prompt MUST be updated to explicitly steer the agent toward summary tools before raw fetches, including guidance on when to use each tool.
- **FR-009**: The `pcp_quick_investigate` tool MUST live in `tools/investigate.py` and follow the existing `_*_impl()` test-injection pattern so it can be unit-tested without a live pmproxy connection.

### Key Entities

- **Investigation Request**: A time of interest plus optional scope parameters (subsystem filter, lookback window, baseline period).
- **Anomaly Summary**: A ranked list of structured JSON objects, each containing: `metric` (name), `score` (float, anomaly severity), `direction` (up/down), `magnitude` (numeric change), and `summary` (brief human-readable label) — bounded to at most 50 results per FR-003.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An agent responding to an open-ended investigation question makes its first call to a summary or investigation tool (not `pcp_fetch_timeseries`) in at least 90% of observed discovery sessions.
- **SC-002**: The new tool can be called with only a `time_of_interest` parameter and returns a meaningful result without error.
- **SC-003**: Output token count for a typical open-ended investigation is reduced by at least 70% compared to the current `pcp_fetch_timeseries`-first pattern (from ~15k tokens to ~4.5k or fewer).
- **SC-004**: The tool returns a result within the same latency envelope as the existing `pcp_detect_anomalies` tool (no additional round-trips beyond what anomaly detection already performs).
- **SC-005**: Unit tests for the new tool achieve the project coverage gate of ≥80% branch coverage using mocked pmproxy responses.

## Clarifications

### Session 2026-03-05

- Q: How should the tool discover metrics to feed into anomaly detection? → A: Call `pcp_discover_metrics` first to enumerate available metrics, then feed them into anomaly detection (dynamic discovery, no hardcoded list).
- Q: How should the tool handle errors from underlying tools (e.g., pcp_detect_anomalies failures, pmproxy timeouts)? → A: Fail fast — propagate the error with a clear message explaining what failed and suggesting the user check pmproxy health. No silent fallback or partial results.
- Q: What output format should the anomaly summary use? → A: Structured JSON — each anomaly as a JSON object with typed fields (metric, score, direction, magnitude, summary). Agent handles presentation.
- Q: What should the new tool be named? → A: `pcp_quick_investigate` — follows `pcp_*` convention, signals low-friction smart-defaults nature.
- Q: Which module should the new tool live in? → A: New module `tools/investigate.py` — dedicated file, keeps orchestration logic separate from existing tool groups.

## Assumptions

- Issue #18 ("Server disconnected" in `pcp_detect_anomalies`) is either fixed before this feature ships, or this feature's wrapper handles the error gracefully and surfaces it clearly rather than silently falling back to raw fetches.
- The default lookback of 2 hours and baseline of 7 days are appropriate for the typical PCP deployment targeted by this tool; these can be overridden via optional parameters.
- "Subsystem" filtering is implemented as a metric name prefix/category match (e.g., `disk.*`, `network.*`) rather than a formal taxonomy — consistent with how other tools in this codebase handle grouping.
- The token budget cap (FR-003) is enforced by limiting the number of returned anomaly results, not by truncating the response mid-record.
