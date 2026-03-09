# Feature Specification: Specialist Agent Investigation Coordinator

**Feature Branch**: `010-specialist-agents`
**Created**: 2026-03-09
**Status**: Draft
**Input**: User description: "Issue #27 — distributed agent model with specialist sub-agents for concurrent performance investigation. Fix metric discovery limits that blind agents to available metric types."

## Clarifications

### Session 2026-03-09

- Q: Should specialists be six separate MCP prompt registrations or one parameterized prompt with a `subsystem` parameter? → A: One parameterized `specialist_investigate` prompt with `subsystem` parameter — domain knowledge keyed per subsystem internally. Start with this; revisit if the per-subsystem content grows too large for one prompt.
- Q: Is bumping `pcp_search` limit the right fix for metric visibility? → A: No — the primary fix is structural: specialist prompts mandate namespace-scoped discovery via `pcp_discover_metrics(prefix=)`, which avoids search ranking bias entirely. Bump `pcp_search` default from 20→50 as a secondary "don't be daft" improvement, but it's not the core solution.
- Q: What strategy should the cross-cutting agent use? → A: Use `pcp_quick_investigate` with no subsystem filter for a broad anomaly scan, then focus on correlations that span multiple subsystems. No independent deep-dive — that's the specialists' job.
- Q: Should specialist findings follow a structured report format? → A: Yes — lightweight consistent structure (metric, severity, direction, summary) matching existing `pcp_quick_investigate` output shape. Makes cross-referencing reliable without being rigid.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Parallel Specialist Investigation (Priority: P1)

A systems engineer reports "the app is slow." The coordinator prompt instructs the calling LLM to dispatch **specialist sub-agents** — one per subsystem (CPU, Memory, Disk, Network, Process) plus a Cross-cutting agent. Each specialist carries deep domain knowledge about what to look for, what metric relationships matter, and how to interpret findings in context. All six run concurrently, then the coordinator synthesises their findings into a unified root-cause narrative.

**Why this priority**: This is the core value proposition — turning a sequential 15-minute investigation into a parallel 3-minute one, with better results because each agent is a domain expert rather than a generalist following namespace hints.

**Independent Test**: Can be tested by invoking the coordinator prompt and verifying it produces dispatch instructions for all six specialist agents with domain-specific investigation guidance.

**Acceptance Scenarios**:

1. **Given** a coordinator prompt invocation with a time of interest, **When** the prompt is rendered, **Then** it contains dispatch instructions for all six specialist agents (CPU, Memory, Disk, Network, Process, Cross-cutting) with distinct domain expertise in each.
2. **Given** a specialist agent prompt for "memory", **When** it runs its investigation, **Then** it follows memory-specific investigation logic: checking swap activity first, correlating `mem.util.used` with page-in/out rates, checking OOM killer activity — not just "look at the `mem.*` namespace."
3. **Given** all six specialists return findings, **When** the coordinator synthesises, **Then** it cross-references findings (e.g., memory pressure agent flagged swap activity + disk agent flagged high iowait = corroborated memory-pressure-induced I/O storm).

---

### User Story 2 — Adequate Metric Coverage During Discovery (Priority: P1)

When any agent (specialist or otherwise) discovers metrics via search, it must see a representative spread of metric **types**, not just the first N results dominated by a single namespace. Currently the default `limit=20` on `pcp_search` means a broad search for "utilisation" returns 20 CPU metrics and zero memory/disk metrics — the agent literally cannot see what it previously retrieved in a different call.

**Why this priority**: Without this fix, specialist agents are hobbled at the discovery step. Equal priority with Story 1 because specialists without adequate discovery are specialists without data.

**Independent Test**: Can be tested by calling `pcp_search` with a broad query and verifying the limit is high enough to return metrics across multiple subsystems.

**Acceptance Scenarios**:

1. **Given** an agent searches for metrics with a broad term, **When** the search returns results, **Then** the default limit returns enough results to cover metrics across multiple subsystem namespaces (not dominated by a single namespace).
2. **Given** a specialist agent uses search within its domain, **When** the search executes, **Then** the specialist prompt guidance instructs it to use an adequate limit and/or use namespace-scoped discovery rather than broad search.

---

### User Story 3 — Specialist Domain Prompts (Priority: P2)

Each subsystem gets a dedicated specialist prompt that encodes deep sysadmin domain knowledge. A CPU specialist knows to check steal time on VMs, runqueue depth for scheduler saturation, and per-CPU imbalance for SMP issues. A Memory specialist knows that any swap activity is an emergency signal. A Disk specialist correlates IOPS with latency and checks queue saturation. These aren't generic "look at namespace X" instructions — they're the reasoning of an experienced performance engineer.

**Why this priority**: The current `investigate_subsystem` prompt provides namespace hints but no deep domain reasoning. Specialist prompts are the differentiator that makes parallel investigation produce better results than sequential.

**Independent Test**: Can be tested by rendering each specialist prompt and verifying it contains domain-specific investigation logic, metric relationships, and interpretation guidance unique to that subsystem.

**Acceptance Scenarios**:

1. **Given** a CPU specialist prompt, **When** rendered, **Then** it contains investigation steps specific to CPU: steal time checks for VMs, per-CPU imbalance analysis, runqueue depth vs load average correlation, and user/sys ratio interpretation.
2. **Given** a Disk specialist prompt, **When** rendered, **Then** it contains disk-specific logic: IOPS-vs-latency correlation, queue depth saturation detection, device-level hotspot identification, and sequential-vs-random I/O pattern analysis.
3. **Given** a Network specialist prompt, **When** rendered, **Then** it contains network-specific logic: error-rate vs throughput correlation, per-interface analysis, dropped-packet significance assessment, and bandwidth saturation detection.

---

### User Story 4 — Coordinator Steers LLM Entry Point (Priority: P3)

The coordinator prompt is positioned as the **entry point** for broad investigations. Session initialisation and prompt descriptions guide the calling LLM to use the coordinator for open-ended investigation requests, rather than going straight to individual tools or the existing `investigate_subsystem` prompt.

**Why this priority**: Discoverability ensures the coordinator is actually used. Lower priority because it's a UX refinement — the feature works without it, it's just harder to find.

**Independent Test**: Can be tested by checking that session_init prompt text references the coordinator, and that prompt descriptions position it as the primary investigation entry point.

**Acceptance Scenarios**:

1. **Given** a user asks an LLM "investigate why the app is slow", **When** the LLM reads available prompt descriptions, **Then** the coordinator prompt's description clearly positions it as the entry point for broad investigation.
2. **Given** the session_init prompt is invoked, **When** rendered, **Then** it includes guidance to use the coordinator prompt for investigation requests.

---

### Edge Cases

- What happens when a specialist agent finds **no metrics** for its subsystem? It should report "no metrics found for [subsystem]" and bail early — this is useful signal (rules out that subsystem).
- What happens when only **some** specialist agents complete (others timeout or error)? The coordinator synthesis must work with partial results, noting which subsystems could not be investigated.
- What happens when the calling LLM **cannot dispatch in parallel** (e.g., Claude Desktop without sub-agent support)? The coordinator prompt must include a sequential fallback instruction.
- What happens when **cross-cutting correlations** emerge (e.g., swap + iowait)? The synthesis phase must explicitly cross-reference findings across specialist reports.
- What happens when the search limit returns results **all from one namespace**? The specialist should use namespace-scoped discovery (`pcp_discover_metrics` with `prefix=`) rather than relying on broad search.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a coordinator prompt (`coordinate_investigation`) that instructs the calling LLM to dispatch specialist sub-agents for concurrent investigation.
- **FR-002**: System MUST provide a single parameterized `specialist_investigate` prompt with a `subsystem` parameter that dispatches to domain-specific investigation knowledge for each of the six subsystems (CPU, Memory, Disk, Network, Process, Cross-cutting).
- **FR-003**: Each specialist prompt MUST contain investigation logic specific to its domain (metric relationships, interpretation heuristics, severity thresholds), not just namespace hints.
- **FR-004**: The coordinator prompt MUST include synthesis instructions for cross-referencing findings across all specialist reports into a unified root-cause narrative.
- **FR-005**: The coordinator prompt MUST be capability-aware — instructing parallel dispatch when the client supports it, with a sequential fallback when it does not.
- **FR-006**: The coordinator MUST handle partial results gracefully — synthesise whatever specialist reports are available, noting which subsystems could not be investigated.
- **FR-007**: The `pcp_search` tool's default limit MUST be increased from 20 to 50 as a secondary improvement for general use. This is not the primary fix for metric visibility — search ranking bias means higher limits still favour dominant namespaces.
- **FR-008**: Specialist prompts MUST mandate namespace-scoped discovery via `pcp_discover_metrics(prefix=)` as the primary metric discovery mechanism. This avoids search ranking bias entirely — each specialist walks its own namespace tree. `pcp_search` is only for keyword-based exploration when the metric name is unknown.
- **FR-009**: The `session_init` prompt MUST be updated to reference the coordinator as the recommended entry point for broad investigation.
- **FR-010**: Each specialist prompt MUST follow the existing `_*_impl()` pattern for testability.
- **FR-011**: The coordinator prompt MUST accept parameters: `request` (what to investigate), `host` (optional), `time_of_interest` (optional, defaults to "now"), and `lookback` (optional, defaults to "2hours").

### Key Entities

- **Coordinator Prompt**: Orchestration layer that dispatches specialist agents, collects results, and synthesises findings. Not a tool — a prompt that shapes LLM behaviour.
- **Specialist Prompt**: Domain-specific investigation prompt encoding deep sysadmin knowledge for one subsystem. Returns structured guidance for investigation workflow within that domain.
- **Specialist Report**: The output format each specialist produces — a consistent lightweight structure per finding (metric, severity, direction, summary) matching the existing `pcp_quick_investigate` output shape, plus a subsystem-level assessment. Consumed by the coordinator's synthesis phase for cross-referencing.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A full-system investigation using the coordinator covers all six subsystems in the time it previously took to investigate one sequentially (when the client supports parallel dispatch).
- **SC-002**: Each specialist prompt contains at least 5 domain-specific investigation steps or heuristics that go beyond namespace hints (e.g., "check steal time on VMs", "correlate IOPS with latency").
- **SC-003**: Broad metric search queries return results from at least 3 distinct metric namespaces (not concentrated in one namespace due to low default limits).
- **SC-004**: The coordinator's synthesis phase produces cross-subsystem correlations when related anomalies are found by different specialists (e.g., memory pressure + disk I/O).
- **SC-005**: Investigations produce actionable root-cause narratives, not just lists of anomalous metrics — each finding includes severity, context, and recommended next steps.

## Assumptions

- The calling LLM client (Claude Code, Claude Desktop, etc.) supports dispatching sub-agents or can at minimum execute prompts sequentially. The coordinator is designed to work with both modes.
- The existing `investigate_subsystem` prompt will be retained as a simpler alternative — the specialist prompts supersede it for deep investigation but don't replace it.
- The existing tool infrastructure (`pcp_quick_investigate`, `pcp_detect_anomalies`, `pcp_fetch_timeseries`, etc.) is sufficient for specialist agents — no new tools are needed, only new prompts.
- The `pcp_search` limit fix is a small, backward-compatible change — increasing a default parameter value.
