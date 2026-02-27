# Implementation Plan: MCP Prompts — Investigation Workflow Templates

**Branch**: `003-mcp-prompts` | **Date**: 2026-02-27 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/003-mcp-prompts/spec.md`

## Summary

Implement four MCP Prompt templates (`investigate_subsystem`, `incident_triage`, `compare_periods`, `fleet_health_check`) that encode expert SRE investigation workflows, making them available to any MCP-compatible client. Each prompt is a pure Python function decorated with `@mcp.prompt()` that returns a structured list of messages seeding an AI investigation conversation. Four existing Claude Code-specific agent files are retired incrementally alongside their corresponding prompts. E2E tests are deferred pending `pmlogger-synth` (issue #13); unit and contract tests provide full coverage of prompt structure and registration.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: `mcp[cli]` ≥1.26.0 (FastMCP `@mcp.prompt()` decorator), `pytest`, `pytest-asyncio`
**Storage**: N/A — prompts are stateless pure functions returning text templates
**Testing**: `pytest`, `pytest-asyncio`; no `respx` needed (prompts make no HTTP calls)
**Target Platform**: Any MCP-compatible client (Claude Desktop, IDE integrations, custom apps)
**Project Type**: Single — extends existing `src/pmmcp/` package
**Performance Goals**: Prompt generation is instantaneous (pure function, no I/O); no latency SLA
**Constraints**: No external I/O in prompt functions; all content is static text with argument interpolation
**Scale/Scope**: 4 prompt modules, each ≤200 lines; 4 unit test files, 1 contract test file

## Constitution Check

| Principle | Status | Notes / Justification |
|-----------|--------|----------------------|
| I. Code Quality — linting enforced, single-responsibility, complexity ≤ 10, peer review | **PASS** | `ruff` lint + format enforced in CI; each prompt module has single responsibility; pure functions have complexity ≤ 3 |
| II. Testing Standards — TDD cycle, ≥ 80% unit coverage, contract tests on interface changes | **PASS** | TDD applied per story; contract tests cover all 4 prompt schemas + message structure; E2E deferred with documented justification (issue #13) |
| III. UX Consistency — design system adherence, WCAG 2.1 AA, actionable error messages | **N/A** | No UI components; MCP prompts are text templates consumed by AI clients, not rendered as UI |
| IV. Performance — latency SLA defined, performance budget in CI, profiling before optimization | **N/A** | Prompts are pure functions with no measurable latency; no runtime computation beyond string formatting |
| V. Simplicity — YAGNI posture, no speculative abstractions, complexity justified below | **PASS** | Four plain functions in four modules; no shared abstraction layer introduced; no generalisation beyond current need |

## Project Structure

### Documentation (this feature)

```text
specs/003-mcp-prompts/
├── plan.md              ← this file
├── research.md          ← Phase 0 complete
├── spec.md              ← feature specification
├── checklists/
│   └── requirements.md
└── tasks.md             ← Phase 2 output (/speckit.tasks)
```

### Source Code

```text
src/pmmcp/
├── server.py            ← add: import pmmcp.prompts (side-effect registration)
└── prompts/             ← new package
    ├── __init__.py      ← imports all four modules (triggers @mcp.prompt registration)
    ├── investigate.py   ← investigate_subsystem prompt
    ├── triage.py        ← incident_triage prompt
    ├── compare.py       ← compare_periods prompt
    └── health.py        ← fleet_health_check prompt

tests/
├── unit/
│   ├── test_prompts_investigate.py   ← new
│   ├── test_prompts_triage.py        ← new
│   ├── test_prompts_compare.py       ← new
│   └── test_prompts_health.py        ← new
└── contract/
    └── test_prompts.py               ← new (schema + message structure)

agents/                  ← retiring incrementally (see Story order below)
├── performance-investigator.md  ← deleted with Story 1
├── metric-explorer.md           ← deleted with Story 1
├── performance-comparator.md    ← deleted with Story 3
└── performance-reporter.md      ← deleted with Story 4
```

**Structure Decision**: Single project extension. All prompts live under `src/pmmcp/prompts/`, mirroring the `src/pmmcp/tools/` layout. No new service or layer introduced (Principle V).

---

## Implementation Order & TDD Workflow

Stories are implemented one at a time, each as a complete Red-Green-Refactor cycle per Constitution v1.2.0 Principle II. The mandatory per-story loop is:

```
1. Write failing tests  →  commit: "test: <story>"
2. Implement            →  tests pass
3. Refactor             →  clean up
4. Run pre-push-sanity  →  lint + format + unit + integration all green
5. Commit + push        →  commit: "feat: <story>"
```

---

### Infra Commit (prerequisite — before Story 1)

**What**: Create `src/pmmcp/prompts/__init__.py` (empty) and add `import pmmcp.prompts` to `server.py`.

**Why first**: Ensures the package is importable before any prompt module is written. Contract tests import `pmmcp.server`, so the registration hook must exist.

**Commit**: `chore: add prompts package skeleton and server registration hook`

---

### Story 1 (P1) — `investigate_subsystem` + retire investigator + explorer agents

**Spec reference**: User Story 1 — Guided Subsystem Investigation

**Content absorbed from retiring agents**:
- `agents/performance-investigator.md`: triage workflow, subsystem hints (CPU/mem/disk/net/proc namespaces), hierarchical sampling strategy, metric families, presentation standards
- `agents/metric-explorer.md`: namespace hierarchy table, metric semantics, exploration strategy

**Test targets** (`test_prompts_investigate.py`):
- Returns ≥1 message for all 6 subsystem values
- Message content includes discovery-first instruction
- Each subsystem has natural-language namespace hints (not hardcoded metric names)
- Presentation standards present (CPU as %, memory in GB, bandwidth in Mbps, disk in MB/s)
- Missing-tool abort instruction present (FR-017)
- No-metrics-found stop instruction present (FR-018)
- Timerange out-of-retention stop instruction present (FR-019)
- `symptom` argument interpolated when provided
- `host` argument interpolated when provided

**Contract targets** (`test_prompts.py`):
- `investigate_subsystem` registered with correct argument schema
- `subsystem` required; `host`, `timerange`, `symptom` optional
- Returns non-empty well-formed message list

**Files changed**:
- `src/pmmcp/prompts/investigate.py` (new)
- `src/pmmcp/prompts/__init__.py` (add import)
- `tests/unit/test_prompts_investigate.py` (new)
- `tests/contract/test_prompts.py` (new — starts with investigate_subsystem assertions)
- `agents/performance-investigator.md` (deleted)
- `agents/metric-explorer.md` (deleted)

**Commits**:
1. `test: add failing tests for investigate_subsystem prompt`
2. `feat: implement investigate_subsystem prompt + retire performance-investigator and metric-explorer agents`

---

### Story 2 (P2) — `incident_triage`

**Spec reference**: User Story 2 — Live Incident Triage

**No agent to retire** (new capability, no prior agent).

**Test targets** (`test_prompts_triage.py`):
- Returns ≥1 message
- Symptom-to-subsystem mapping guidance present (latency/slow → CPU/disk/net; OOM → memory; timeout → network/proc)
- Fleet-wide vs host-specific scope confirmation instruction present (FR-012)
- General-sweep fallback instruction for unmappable symptoms present (FR-022)
- Missing-tool abort instruction present (FR-017)
- Timerange out-of-retention stop instruction present (FR-019)
- `symptom` argument interpolated in message
- `host` argument interpolated when provided

**Contract targets**:
- `incident_triage` registered
- `symptom` required; `host`, `timerange` optional (no `severity` — confirmed removed)
- Returns non-empty well-formed message list

**Files changed**:
- `src/pmmcp/prompts/triage.py` (new)
- `src/pmmcp/prompts/__init__.py` (add import)
- `tests/unit/test_prompts_triage.py` (new)
- `tests/contract/test_prompts.py` (extended)

**Commits**:
1. `test: add failing tests for incident_triage prompt`
2. `feat: implement incident_triage prompt`

---

### Story 3 (P2) — `compare_periods` + retire comparator agent

**Spec reference**: User Story 3 — Before/After Period Comparison

**Content absorbed from retiring agent**:
- `agents/performance-comparator.md`: comparison methodology, hierarchical approach, statistical interpretation, significance threshold guidance

**Test targets** (`test_prompts_compare.py`):
- Returns ≥1 message
- Broad-scan-first instruction present (FR-007)
- Ranks results by magnitude instruction present (FR-007)
- Root-cause hypothesis instruction present (FR-007)
- Overlap detection instruction present (FR-020)
- Timerange out-of-retention stop instruction present (FR-019)
- Missing-tool abort instruction present (FR-017)
- `context` argument interpolated when provided
- `host` argument interpolated when provided
- `subsystem` argument scopes the scan when provided

**Contract targets**:
- `compare_periods` registered
- `baseline_start`, `baseline_end`, `comparison_start`, `comparison_end` required
- `host`, `subsystem`, `context` optional
- Returns non-empty well-formed message list

**Files changed**:
- `src/pmmcp/prompts/compare.py` (new)
- `src/pmmcp/prompts/__init__.py` (add import)
- `tests/unit/test_prompts_compare.py` (new)
- `tests/contract/test_prompts.py` (extended)
- `agents/performance-comparator.md` (deleted)

**Commits**:
1. `test: add failing tests for compare_periods prompt`
2. `feat: implement compare_periods prompt + retire performance-comparator agent`

---

### Story 4 (P3) — `fleet_health_check` + retire reporter agent

**Spec reference**: User Story 4 — Fleet-Wide Health Check

**Content absorbed from retiring agent**:
- `agents/performance-reporter.md`: KPI table format, per-subsystem default metrics, presentation standards, concern thresholds, trend classification

**Test targets** (`test_prompts_health.py`):
- Returns ≥1 message
- Host enumeration instruction present (FR-021 — check for empty fleet)
- No-hosts-found abort instruction present (FR-021)
- Summary table format instruction present (FR-009)
- Default subsystems instruction present (cpu, memory, disk, network)
- `detail_level=detailed` drill-down instruction present (FR-008)
- `subsystems` argument scopes the sweep when provided
- `timerange` argument scopes the window when provided
- Missing-tool abort instruction present (FR-017)
- No-metrics-found stop instruction present (FR-018)
- Timerange out-of-retention stop instruction present (FR-019)

**Contract targets**:
- `fleet_health_check` registered
- `timerange`, `subsystems`, `detail_level` all optional
- Returns non-empty well-formed message list

**Files changed**:
- `src/pmmcp/prompts/health.py` (new)
- `src/pmmcp/prompts/__init__.py` (finalised)
- `tests/unit/test_prompts_health.py` (new)
- `tests/contract/test_prompts.py` (finalised — all 4 prompts covered)
- `agents/performance-reporter.md` (deleted)

**Commits**:
1. `test: add failing tests for fleet_health_check prompt`
2. `feat: implement fleet_health_check prompt + retire performance-reporter agent`

---

## Cross-Cutting Concerns

### E2E Tests — Deferred

Full end-to-end tests for prompt-driven investigation workflows require deterministic pmlogger archive data pre-ingested into pmproxy. This depends on `pmlogger-synth` (issue #13), tracked as a separate body of work. E2E tests for this feature are explicitly deferred.

**Coverage without E2E**: Unit tests (prompt content assertions) + contract tests (schema + message structure) provide sufficient confidence that prompts are correctly implemented. The underlying tool calls invoked during an AI-driven investigation are covered by the existing `tests/integration/` suite.

### Constitution & CLAUDE.md Amendments

Per the user's requirement, two amendments are applied as part of this plan:

1. **Constitution v1.2.0** — Principle II amended to add story-scoped TDD decomposition requirement: each story MUST complete a full Red-Green-Refactor cycle before the next begins, with tests committed before implementation.

2. **CLAUDE.md** — Add explicit "Story-by-Story Development Loop" section documenting the mandatory per-story workflow.

These amendments are committed ahead of implementation:
- `docs: amend constitution v1.2.0 — story-scoped TDD development loop`
- Applied as part of the infra setup commit, before Story 1.

### Pre-Push Sanity

Every push in this feature MUST be preceded by:
```bash
scripts/pre-push-sanity.sh
```
Or via the `/pre-push-sanity` skill. This is already mandated by Constitution v1.1.0 Principle II and reinforced in v1.2.0.

---

## Complexity Tracking

No violations to document. All Constitution principles pass or are explicitly N/A for this feature type.
