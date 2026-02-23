<!--
SYNC IMPACT REPORT
==================
Version change: [template/unratified] → 1.0.0 (initial ratification)

Principles added (all new):
  - I. Code Quality
  - II. Testing Standards
  - III. User Experience Consistency
  - IV. Performance Requirements
  - V. Simplicity & Evolutionary Design

Sections added:
  - Technical Decision Framework (new)
  - Quality Gates & Compliance Review (new)
  - Governance (new)

Templates updated:
  ✅ .specify/memory/constitution.md — this file (written, v1.0.0)
  ✅ .specify/templates/plan-template.md — Constitution Check gates updated with concrete principle checks
  ✅ .specify/templates/tasks-template.md — test optionality note aligned with Principle II (NON-NEGOTIABLE)
  ✅ .specify/templates/spec-template.md — Success Criteria section; no structural change required, alignment confirmed

Deferred TODOs:
  - TODO(PROJECT_NAME): "pmmcp" inferred from repository directory; confirm display name or acronym expansion.
  - TODO(TONE_GUIDE): Principle III references a tone and terminology guide; create docs/ux-terminology.md
    when UX content standards are established.
  - TODO(ADR_DIR): Technical Decision Framework references docs/decisions/ for ADRs; directory does not
    yet exist — create on first architectural decision.
-->

# PMMCP Constitution

## Core Principles

### I. Code Quality

Code is read far more often than it is written. Every function, module, and component MUST be
clean, comprehensible, and internally consistent.

- All code MUST pass automated linting and formatting checks before merge.
- Functions MUST do one thing; files MUST have a single, clearly stated responsibility.
- Cyclomatic complexity MUST NOT exceed 10 per function without documented justification in the
  feature plan's Complexity Tracking table.
- Code reviews MUST be completed by at least one peer before merging to any protected branch.
- Dead code, commented-out blocks, and orphaned files MUST be removed rather than retained.
- All dependencies MUST be explicitly declared; implicit transitive reliance is prohibited.

**Rationale**: Technical debt compounds. Defects caught at review time cost an order of magnitude
less to fix than those discovered post-deployment. Consistent quality lowers onboarding time and
reduces cognitive overhead for the entire team.

### II. Testing Standards (NON-NEGOTIABLE)

Tests are the executable specification of the system's intent. Coverage is not optional.

- The TDD cycle MUST be followed: write failing test → implement → refactor (Red-Green-Refactor).
- Unit test coverage MUST NOT drop below 80% on any merged feature branch.
- Integration tests MUST cover all public API contracts and inter-service communication boundaries.
- Unit tests MUST be isolated and repeatable; all external I/O MUST be mocked or stubbed.
- No feature is considered complete until all tests pass in CI without modification or skip.
- Performance regression tests MUST be included for any code path with a defined latency SLA.
- Contract tests MUST be written whenever a public interface changes.

**Rationale**: Tests provide the safety net that enables confident refactoring, continuous delivery,
and fearless evolution of the system over time.

### III. User Experience Consistency

Every user-facing surface MUST conform to a shared design language. Inconsistency erodes trust
and increases support burden.

- All UI components MUST originate from or conform to the established design system.
- Interaction patterns — navigation, error display, loading states, confirmation dialogs — MUST
  be identical across equivalent contexts throughout the product.
- Accessibility MUST meet WCAG 2.1 AA standards at minimum; AA exceptions require explicit
  documented justification.
- Error messages MUST be human-readable, actionable, and free of internal stack traces or
  technical jargon not relevant to the user.
- All user-visible copy MUST follow the project tone and terminology guide
  (see TODO(TONE_GUIDE) above).

**Rationale**: Users form mental models quickly. Deviations from established patterns require
re-learning, create friction, and undermine confidence in the product.

### IV. Performance Requirements

Performance is a first-class feature, not a post-launch concern. Degradation is regression.

- Every user-facing response path MUST have a defined latency SLA (e.g., p95 < 200 ms) recorded
  in the feature plan before implementation begins.
- Performance budgets (payload size, startup time, query count per request) MUST be defined in
  the plan and enforced in CI via automated checks.
- Any change that regresses a defined SLA by more than 5% MUST be rejected or accompanied by a
  documented exception approved by at least one team member.
- Profiling data MUST be collected and reviewed before any performance-motivated optimization
  is undertaken; no premature optimization.
- Caching, lazy loading, and pagination MUST be the default approach for data-heavy operations.

**Rationale**: Performance problems discovered in production are exponentially harder to fix than
those caught during development, and they directly impact user satisfaction and retention.

### V. Simplicity & Evolutionary Design

The best code is the code that does not exist. Build the minimum necessary to satisfy current
requirements, and refactor continuously.

- YAGNI (You Aren't Gonna Need It) MUST be the default posture; no speculative abstractions or
  premature generalization.
- Abstractions MUST be introduced only when a pattern repeats three or more times across
  independent contexts.
- Architectural complexity — additional services, layers, or patterns — MUST be justified in the
  Complexity Tracking table of the feature plan.
- Refactoring MUST be a continuous practice; each contribution MUST leave the codebase in at
  least as good a state as it was found (Boy Scout Rule).
- Technology choices MUST favour established, well-documented solutions over novelty for its
  own sake.

**Rationale**: Simple systems are easier to debug, onboard, and evolve. Unnecessary complexity is
the primary source of defects and the primary obstacle to sustainable velocity.

## Technical Decision Framework

When a technical decision must be made, apply this hierarchy in order:

1. **Principle violation check**: Does the decision violate any Core Principle? If yes, it MUST
   be rejected or escalated with full team review before proceeding.
2. **Complexity gate (Principle V)**: Does the decision introduce architectural complexity beyond
   current need? If yes, document justification in the plan's Complexity Tracking table.
3. **Performance impact (Principle IV)**: Does the decision affect any defined performance SLA?
   If yes, a measurable performance impact assessment MUST accompany the proposal.
4. **UX review (Principle III)**: Does the decision alter any user-facing behavior or pattern?
   If yes, UX review MUST be completed before implementation begins.
5. **Coverage gate (Principle II)**: Does the decision reduce test coverage below defined
   thresholds? If yes, the decision MUST NOT be merged as-is.
6. **Quality gate (Principle I)**: Does the decision require bypassing linting, formatting, or
   review requirements? If yes, the decision MUST NOT be merged as-is.

All architectural decisions with cross-feature impact MUST be recorded as Architecture Decision
Records (ADRs) in `docs/decisions/` (see TODO(ADR_DIR) above).

## Quality Gates & Compliance Review

Every pull request MUST pass all of the following gates before merge:

- [ ] Linting and formatting checks pass in CI (Principle I)
- [ ] All pre-existing tests continue to pass in CI (Principle II)
- [ ] New code achieves ≥ 80% unit test coverage (Principle II)
- [ ] All public interface changes have corresponding contract tests (Principle II)
- [ ] Performance budget checks pass in CI (Principle IV)
- [ ] At least one peer code review approved (Principle I)
- [ ] Constitution Check section in `plan.md` completed with pass/fail per principle (all)
- [ ] Any principle violations documented in the Complexity Tracking table with justification

Compliance reviews MUST be conducted at the start of each feature (Constitution Check in
`plan.md`) and again at the close of each milestone before release sign-off.

## Governance

This constitution supersedes all other team agreements, informal conventions, and prior coding
standards documents. Where conflicts exist between this document and any other guideline, this
constitution takes precedence.

**Amendment Procedure**:

1. Propose the change in writing, referencing the specific section being amended and the rationale.
2. All active contributors MUST have the opportunity to review and provide feedback within
   5 business days.
3. Amendments require explicit approval from at least two contributors.
4. Approved amendments MUST increment the version per the versioning policy below.
5. All affected templates and dependent artifacts MUST be updated in the same commit or PR as
   the amendment.
6. `LAST_AMENDED_DATE` MUST be updated to the merge date of the amending PR.

**Versioning Policy**:

- **MAJOR**: Principle removal, redefinition, or backward-incompatible governance change.
- **MINOR**: New principle, new section, or materially expanded guidance.
- **PATCH**: Clarifications, wording improvements, or non-semantic refinements.

**Compliance Review**:

Every feature plan MUST include a Constitution Check section with explicit pass/fail status for
each of the five Core Principles. Violations MUST be tracked in the Complexity Tracking table
with documented justification. Any feature that bypasses a quality gate without documented
justification MUST be raised as a retrospective action item.

For runtime development guidance and active technology context, see agent files in `.claude/`.

---

**Version**: 1.0.0 | **Ratified**: 2026-02-20 | **Last Amended**: 2026-02-20
