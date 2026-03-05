# Research: Investigation UX Improvements

**Feature**: 005-investigation-ux
**Phase**: 0 — All NEEDS CLARIFICATION resolved from spec's Clarifications section (2026-03-04)

---

## Decision: Derived Metric Expressions

**Decision**: Use the three canonical PCP derived metric expressions as specified:
- `derived.cpu.utilisation` = `100 - rate(kernel.all.cpu.idle) / hinv.ncpu / 10`
- `derived.disk.utilisation` = `rate(disk.all.avactive) / 10`
- `derived.mem.utilisation` = `100 * mem.util.used / mem.physmem`

**Rationale**: Directly specified by the product owner with explicit reasoning:
- CPU: idle-complement captures all non-idle states (user/sys/nice/wait/steal) cross-platform
- Disk: aggregate busy time across all devices; per-device breakdown stays in existing tools
- Memory: used/physical % is the most universally understood memory pressure signal

**Alternatives considered**: Per-CPU breakdown, swap-based pressure — rejected as out of scope for session defaults.

---

## Decision: Idempotency Strategy for session_init

**Decision**: Re-register unconditionally on every `session_init` invocation — no guard logic.

**Rationale**: `pcp_derive_metric` silently overwrites an existing registration with the same name (confirmed in clarifications). Idempotency is free; adding guard logic (e.g., checking if already registered) would add complexity with zero benefit.

**Alternatives considered**: Check-before-register — rejected because there is no "list derived metrics" API in pmproxy, making pre-check impossible without extra scaffolding.

---

## Decision: session_init Verification Step

**Decision**: The prompt instructs Claude to call `pcp_fetch_live` for each derived metric name after registering, and to report any that fail without aborting.

**Rationale**: `pcp_derive_metric` always succeeds (FR-003). Failure surfaces only at fetch time if the underlying counters are absent on the target host. The prompt must prescribe verification to honour FR-004.

**Alternatives considered**: Skip verification step — rejected because partial registration on hosts missing counters would be silently invisible.

---

## Decision: incident_triage Rewrite Scope

**Decision**: Full replacement of `triage.py` prompt content. The four-step sequence (detect → compare → scan → drilldown) becomes the primary spine. Preserved guidance from the old prompt: symptom interpolation, host clause, timerange clause, guard clauses (missing tool, out-of-retention).

**Rationale**: Patching an incorrectly-sequenced prompt leaves contradictory guidance. The old Step 4 ("Rapid Broad Assessment") sent Claude directly to `pcp_fetch_timeseries` — the wrong default. A full rewrite makes the correct sequence unambiguous.

**What stays from old prompt**:
- Symptom/host/timerange interpolation (tested by existing passing tests — must not break)
- Guard clauses (missing tool abort, out-of-retention stop)
- Symptom-to-subsystem mapping table
- Fleet-wide vs host-specific scope check

**What changes**:
- Step 3 (Discovery) and Step 4 (Rapid Broad Assessment) are replaced by the explicit 4-step anomaly → compare → scan → drilldown sequence
- Step transitions use qualitative criteria, not numeric thresholds

---

## Decision: Tool Description Update Scope

**Decision**: Update docstrings in-place for:
1. `pcp_detect_anomalies` — add "Start here" / "first tool" language
2. `pcp_fetch_timeseries` — add "drill-down" / "after anomalies identified" language
3. All tools with user-supplied `limit` param: `pcp_fetch_timeseries`, `pcp_query_series`, `pcp_discover_metrics`, `pcp_get_hosts`, `pcp_search` — add exploration-vs-analysis guidance with concrete default of 50
4. `pcp_scan_changes` — `max_metrics` is analogous to `limit`; add same guidance

**Rationale**: Tool description text is the primary mechanism by which Claude selects tools. Text-only changes have zero runtime risk (no schema changes, no signature changes).

**Alternatives considered**: Adding a new tool alias — rejected (YAGNI; description update is sufficient).

---

## Decision: New Prompt vs Tool for session_init

**Decision**: Implement `session_init` as an MCP **prompt** (not a tool), following the existing prompt pattern.

**Rationale**: The prompt returns instructional text that Claude acts upon. It does not directly call `pcp_derive_metric` itself (a prompt cannot chain tool calls). This matches the established architecture and the spec's explicit statement: "The session-init prompt is a new MCP prompt (not a tool) — it returns instructional text that Claude acts upon."

**Alternatives considered**: Making it a tool that directly registers metrics — rejected by spec; prompts guide Claude's behavior, they don't replace it.

---

## No Open Questions

All NEEDS CLARIFICATION items from the Technical Context have been resolved via:
- Spec Clarifications section (2026-03-04)
- Direct examination of `pcp_derive_metric` behavior
- Existing codebase patterns (prompt pattern, `_*_impl()` pattern)
