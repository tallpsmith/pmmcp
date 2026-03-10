# Research: Specialist Historical Baselining

**Feature**: 011-specialist-baselining | **Date**: 2026-03-10

## Research Tasks & Findings

### R1: How does `pcp_detect_anomalies` work and what does it return?

**Decision**: Use the existing `pcp_detect_anomalies` tool as-is — no modifications needed.

**Findings**:
- Signature: `(metrics, recent_start, recent_end, baseline_start, baseline_end, z_score_threshold=2.0, host="", interval="auto")`
- Returns `list[dict]` with: `metric`, `severity` (critical/warning/info/none), `z_score`, `direction` (higher/lower), `recent_mean`, `recent_stddev`, `baseline_mean`, `baseline_stddev`
- Z-score calculation: `(recent_mean - baseline_mean) / baseline_stddev`
- Already handles the statistical comparison between two time windows

**Rationale**: The tool already accepts arbitrary time windows. The Baseline step just needs to instruct the agent to call it with a 7-day baseline window.

### R2: How should the Baseline step be structured in the workflow?

**Decision**: Insert Baseline as step 2 in the specialist workflow (Discover → **Baseline** → Fetch → Analyse → Report).

**Findings**:
- Current workflow is 4 steps: Discover → Fetch → Analyse → Report
- The Baseline step needs to come after Discover (so we know what metrics exist) but before Fetch (so the live data fetch can be informed by baseline context)
- The Baseline step instructs the agent to:
  1. Fetch 7-day historical data at 1hour interval using `pcp_fetch_timeseries`
  2. Run `pcp_detect_anomalies` comparing investigation window against 7-day baseline
  3. Note anomaly results for use in the Analyse step

**Alternatives considered**:
- Baseline after Fetch: Rejected — agent benefits from knowing baseline context before interpreting live data
- Baseline merged into Analyse: Rejected — separating concerns keeps each step focused

### R3: How should classification (ANOMALY/RECURRING/BASELINE) be assigned?

**Decision**: LLM judgement guided by prompt heuristics — no new tool required.

**Findings**:
- ANOMALY: `pcp_detect_anomalies` returns a significant z-score and the pattern doesn't recur in the 7-day timeseries
- RECURRING: 7-day timeseries shows repeated spikes at consistent times of day (batch jobs, log rotation, backups)
- BASELINE: Current values are within normal range for this host based on the 7-day history
- The specialist examines timeseries shape for time-of-day correlation

**Rationale**: Domain knowledge already references daily patterns. LLM is well-suited to pattern recognition in timeseries shapes described textually. A dedicated periodicity tool would be over-engineering for this iteration.

### R4: How should `severity_despite_baseline` work?

**Decision**: Independent field that carries threshold-based severity regardless of classification.

**Findings**:
- A finding can be BASELINE (normal for this host) but still severity=warning/critical (thresholds exceeded)
- This captures the "your normal is sick" scenario — e.g., CPU idle consistently < 10% for a week
- The specialist articulates this narratively: "this is bad, but based on previous days this is not a new problem"

**Alternatives considered**:
- Merge severity into classification: Rejected — conflates "is this new?" with "is this bad?"
- Separate classification and severity tools: Rejected — over-engineering; the LLM assigns both from the same data

### R5: Cross-cutting specialist — baseline step or not?

**Decision**: No baseline step for cross-cutting. It consumes classifications from domain specialists.

**Findings**:
- Cross-cutting already runs `pcp_quick_investigate` for broad anomaly scanning
- Adding a baseline step would duplicate domain specialists' work
- Cross-cutting's role is correlation, not independent metric analysis
- It receives classification data through domain specialist reports and uses it for prioritisation

### R6: Graceful degradation approach

**Decision**: Prompt-level fallback instructions — no code changes needed.

**Findings**:
- When `pcp_detect_anomalies` returns insufficient data (few or no results), the specialist falls back to threshold-only analysis
- The specialist notes the limitation in its report: "insufficient baseline data, falling back to threshold-only analysis"
- Common causes: new host, recent PCP deployment, archive gaps
- Sparse data (gaps from PCP restarts) still produces results but with reduced confidence — specialist notes this

### R7: Coordinator classification ranking

**Decision**: ANOMALY always ranks above BASELINE/RECURRING, regardless of severity. Severity is secondary sort within each tier.

**Findings**:
- "What changed" is more actionable than "what's chronically wrong"
- Chronic issues (BASELINE with severity warning/critical) are still reported, just after anomalies
- Coordinator synthesis explicitly calls out baseline behaviour to reduce noise
- Highlights when an apparent anomaly matches a known recurring pattern
