# Feature Specification: Specialist Historical Baselining

**Feature Branch**: `011-specialist-baselining`
**Created**: 2026-03-10
**Status**: Draft
**Input**: User description: "Specialists should baseline against historical data to distinguish anomalies from normal behaviour"
**GitHub Issue**: #30

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Specialist findings include anomaly classification (Priority: P1)

When a performance investigation runs, each domain specialist (CPU, Memory, Disk, Network, Process) fetches a 7-day historical baseline for its key metrics and classifies every finding as ANOMALY, RECURRING, or BASELINE. This prevents false alarms on known patterns like daily batch jobs or normal working-set growth.

**Why this priority**: This is the core value proposition — without classification, specialists cry wolf on business-as-usual behaviour, drowning the signal in noise.

**Independent Test**: Invoke `specialist_investigate(subsystem="cpu")` and verify the prompt output includes instructions to fetch a 7-day baseline, run `pcp_detect_anomalies`, and classify each finding.

**Acceptance Scenarios**:

1. **Given** a specialist prompt for any domain subsystem, **When** the prompt is rendered, **Then** it includes a Baseline step between Discover and Fetch that instructs the agent to fetch 7-day historical data and run `pcp_detect_anomalies`.
2. **Given** a specialist prompt for any domain subsystem, **When** the prompt is rendered, **Then** it includes instructions to classify each finding as ANOMALY, RECURRING, or BASELINE with baseline context.
3. **Given** a specialist prompt for any domain subsystem, **When** the prompt is rendered, **Then** the report structure includes `classification`, `baseline_context`, and `severity_despite_baseline` fields.
4. **Given** a specialist prompt for any domain subsystem, **When** the prompt is rendered, **Then** the report guidance instructs the agent to articulate chronic problems narratively (e.g., "this is bad, but based on previous days this is not a new problem — here's what I think is happening").

---

### User Story 2 - Domain knowledge augmented with baseline-aware guidance (Priority: P1)

Each specialist's domain knowledge heuristics are updated to reference the baseline before making threshold-based judgements. For example, the CPU specialist checks whether current CPU levels are typical for this time of day before flagging saturation.

**Why this priority**: Tied with Story 1 — the baseline step is useless if the domain heuristics still say "idle < 10% = saturated" without checking whether that's normal.

**Independent Test**: Read the domain knowledge for each subsystem and verify at least one heuristic references the baseline or `pcp_detect_anomalies`.

**Acceptance Scenarios**:

1. **Given** the CPU specialist domain knowledge, **When** rendered, **Then** it includes guidance to check whether current CPU levels are typical for this time of day over the past week before flagging saturation.
2. **Given** the Memory specialist domain knowledge, **When** rendered, **Then** it includes guidance to compare memory growth against the 7-day baseline to distinguish leaks from normal working-set growth.
3. **Given** the Disk specialist domain knowledge, **When** rendered, **Then** it includes guidance to check whether I/O spikes recur at the same time daily (scheduled jobs like backups, log rotation).
4. **Given** the Network and Process specialist domain knowledge, **When** rendered, **Then** each includes at least one baseline-aware heuristic.

---

### User Story 3 - Cross-cutting specialist prioritises by classification (Priority: P2)

The cross-cutting specialist uses anomaly classifications from domain specialists to prioritise findings. ANOMALY-classified findings are prioritised over RECURRING or BASELINE. Correlated anomalies across multiple subsystems at the same timestamp receive higher confidence.

**Why this priority**: Builds on P1 classifications to improve the cross-cutting correlator's signal-to-noise ratio.

**Independent Test**: Render the cross-cutting specialist prompt and verify it references classification-based prioritisation and correlated anomaly detection.

**Acceptance Scenarios**:

1. **Given** the cross-cutting specialist domain knowledge, **When** rendered, **Then** it includes guidance to prioritise ANOMALY-classified findings over RECURRING or BASELINE.
2. **Given** the cross-cutting specialist domain knowledge, **When** rendered, **Then** it includes guidance to flag correlated anomalies across multiple subsystems at the same timestamp.
3. **Given** the cross-cutting specialist domain knowledge, **When** rendered, **Then** it includes guidance to note when one subsystem reports BASELINE while another reports ANOMALY.

---

### User Story 4 - Coordinator synthesis weights findings by classification (Priority: P2)

The coordinator's synthesis phase leads with anomalies, explicitly calls out baseline behaviour to reduce noise, and highlights when an apparent anomaly matches a known recurring pattern.

**Why this priority**: Final layer of the classification value chain — ensures the end-user report is noise-reduced.

**Independent Test**: Render the `coordinate_investigation` prompt and verify the synthesis section references classification weighting.

**Acceptance Scenarios**:

1. **Given** the coordinator synthesis prompt, **When** rendered, **Then** it includes guidance to always rank ANOMALY findings above BASELINE/RECURRING regardless of severity, with severity as secondary sort within each tier.
2. **Given** the coordinator synthesis prompt, **When** rendered, **Then** it includes guidance to explicitly call out findings that are normal behaviour for the host.
3. **Given** the coordinator synthesis prompt, **When** rendered, **Then** it includes guidance to highlight when an apparent anomaly matches a known recurring pattern.

---

### User Story 5 - Graceful degradation when baseline data is insufficient (Priority: P2)

When a host has less than 7 days of historical data (new host, recent PCP deployment, archive gaps), the specialist gracefully falls back to threshold-only analysis and notes the limitation.

**Why this priority**: Without this, the baseline step would fail or produce misleading results on hosts with limited history.

**Independent Test**: Verify the specialist prompt includes fallback guidance for insufficient baseline data.

**Acceptance Scenarios**:

1. **Given** a specialist prompt, **When** rendered, **Then** it includes instructions to fall back to threshold-only analysis if `pcp_detect_anomalies` returns insufficient data.
2. **Given** a specialist prompt, **When** rendered, **Then** it includes instructions to note "insufficient baseline data, falling back to threshold-only analysis" in the report when degraded.

---

### Edge Cases

- What happens when the host has exactly 0 days of historical data? Specialist falls back entirely to threshold-based analysis with a clear note.
- What happens when baseline data exists but is sparse (e.g., gaps due to PCP restarts)? Specialist should still attempt anomaly detection but note reduced confidence.
- What happens when the 7-day baseline itself is anomalous (e.g., host was under sustained incident for a week)? The classification should still flag current behaviour relative to the available baseline — the specialist cannot know the baseline is "wrong" but the report should note the baseline window.
- What happens when `pcp_detect_anomalies` returns no anomalies? The specialist should report "no anomalies detected relative to 7-day baseline" — this is a valid finding.

## Clarifications

### Session 2026-03-10

- Q: Should BASELINE classification distinguish "normal and healthy" from "normal but degraded"? → A: Keep three classifications (ANOMALY / RECURRING / BASELINE) but add a `severity_despite_baseline` field. A finding can be BASELINE and still carry a severity (warning/critical) based on thresholds. This lets the agent articulate "this is your normal, but your normal is sick."
- Q: How should coordinator rank ANOMALY vs BASELINE findings when severity differs? → A: ANOMALY always ranks above BASELINE/RECURRING regardless of severity. "What changed" is more actionable than "what's chronically wrong." Chronic issues are still reported but after new anomalies.
- Q: How should specialists distinguish RECURRING from BASELINE without a periodicity-detection tool? → A: LLM judgement guided by prompt heuristics. The specialist examines the 7-day timeseries shape for time-of-day correlation (repeated spikes at the same hour). Domain knowledge already references daily patterns (batch jobs, log rotation, backups). No new tooling needed.
- Q: Should the cross-cutting specialist get its own baseline step? → A: No. Cross-cutting consumes and correlates classifications from the 5 domain specialists only. It already runs `pcp_quick_investigate` for broad anomaly scanning — adding a baseline step would duplicate the domain specialists' work.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Each domain specialist prompt (cpu, memory, disk, network, process) MUST include a Baseline step in its workflow between Discover and Fetch. The cross-cutting specialist does NOT get a Baseline step — it consumes and correlates classifications from domain specialists.
- **FR-002**: The Baseline step MUST instruct the agent to fetch 7-day historical data at a coarse interval (e.g., 1hour) using `pcp_fetch_timeseries`.
- **FR-003**: The Baseline step MUST instruct the agent to run `pcp_detect_anomalies` comparing the investigation window against the 7-day baseline.
- **FR-004**: The specialist report structure MUST include a `classification` field with values: ANOMALY, RECURRING, or BASELINE. RECURRING is assigned by LLM judgement when the 7-day timeseries shows repeated spikes at consistent times of day — guided by domain heuristics (batch jobs, log rotation, backups). No dedicated periodicity-detection tool is required.
- **FR-005**: The specialist report structure MUST include a `baseline_context` field providing human-readable comparison to the baseline.
- **FR-005a**: The specialist report structure MUST include a `severity_despite_baseline` field that carries the threshold-based severity (critical/warning/info/none) independently of classification. A BASELINE-classified finding with severity warning or critical indicates a chronic problem — "this is your normal, but your normal is degraded."
- **FR-006**: Each domain specialist's domain knowledge MUST include at least one baseline-aware heuristic relevant to its subsystem.
- **FR-007**: The cross-cutting specialist domain knowledge MUST reference anomaly classification for prioritisation and correlation.
- **FR-008**: The coordinator synthesis phase MUST rank findings with ANOMALY classification above BASELINE/RECURRING regardless of severity. Within each classification tier, findings are sorted by severity (critical → warning → info). Chronic issues (BASELINE/RECURRING with non-zero severity) MUST still be reported, but after anomalies.
- **FR-009**: The specialist prompt MUST include graceful degradation instructions for insufficient baseline data.
- **FR-010**: The investigation flow documentation MUST be updated to reflect the 5-step specialist workflow (Discover → Baseline → Fetch → Analyse → Report).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 5 domain specialist prompts include the Baseline step referencing `pcp_detect_anomalies` in their workflow.
- **SC-002**: All 5 domain specialist prompts include the classification field (ANOMALY / RECURRING / BASELINE), baseline_context, and severity_despite_baseline in their report structure.
- **SC-003**: All 5 domain specialist domain knowledge sections include at least one baseline-aware heuristic.
- **SC-004**: Cross-cutting specialist references classification-based prioritisation in its domain knowledge.
- **SC-005**: Coordinator synthesis phase references classification weighting.
- **SC-006**: Specialist prompts include fallback guidance for insufficient baseline data.
- **SC-007**: Investigation flow diagram shows 5-step workflow (Discover → Baseline → Fetch → Analyse → Report).
- **SC-008**: All unit tests pass, including new tests verifying baseline step and classification presence in prompt output.

## Assumptions

- The 7-day baseline window is a fixed default — not user-configurable in this iteration. This covers daily and weekly recurring patterns, which are the most common. Configurability can be added later if needed.
- The `pcp_detect_anomalies` tool already handles the statistical comparison (z-score based) and does not need modification.
- The `pcp_compare_windows` and `pcp_quick_investigate` tools do not need modification — this feature is purely prompt engineering.
- The classification is advisory — the LLM agent interprets the anomaly detection results and assigns the classification. There is no new tool that automatically classifies.
- Performance impact of the additional baseline fetch is acceptable — the 7-day fetch at 1hour interval is a modest data volume.
- This feature does not change the specialist prompt's function signature — no new parameters are added.

## Scope

### In scope

- Modifications to `src/pmmcp/prompts/specialist.py` (workflow, domain knowledge, report structure)
- Modifications to `src/pmmcp/prompts/coordinator.py` (synthesis guidance)
- Updates to `docs/investigation-flow.md` (workflow diagram)
- Unit tests for prompt output verification

### Not in scope

- Changes to existing tools (`pcp_detect_anomalies`, `pcp_compare_windows`, `pcp_quick_investigate`)
- New tool development
- Making the baseline window configurable
- Changing the `lookback` parameter semantics
