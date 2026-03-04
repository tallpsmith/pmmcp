# Implementation Plan: pmlogsynth Integration

**Branch**: `004-pmlogsynth-integration` | **Date**: 2026-03-03 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/004-pmlogsynth-integration/spec.md`

## Summary

Integrate pmlogsynth as a containerised archive generator that pre-populates valkey with realistic
synthetic PCP performance data before pmproxy starts serving. Pipeline:

```
profiles/*.yml
  → pmlogsynth-generator (one-shot container)
  → pmmcp-archives (named volume)
  → pmlogsynth-seeder (one-shot container)
  → valkey/redis-stack
  → pcp/pmproxy (starts only after seeding completes)
```

No changes to `src/pmmcp/` — this is purely additive compose infrastructure plus new E2E
assertions. Existing tests pass without modification (SC-005).

---

## Technical Context

**Language/Version**: Python 3.8+ (pmlogsynth), Python 3.11 (pmmcp)
**Primary Dependencies**: pmlogsynth (`git+https://github.com/tallpsmith/pmlogsynth`),
  `quay.io/performancecopilot/pcp:latest`, podman compose
**Storage**: Named volume `pmmcp-archives` (ephemeral; purged on `compose down --volumes`)
**Testing**: pytest + pytest-asyncio (existing); new E2E assertions on seeded metric data
**Target Platform**: Linux container (PCP image requires Linux; macOS devs run via VM)
**Project Type**: Single — infrastructure additions only; no new `src/` modules
**Performance Goals**: Startup overhead ≤ 60 seconds increase over baseline (SC-004)
**Constraints**: Generator → seeder → pcp ordering enforced via `depends_on`; seeder waits up to
  60s for valkey readiness; seeder fails fast on any archive load error (all-or-nothing)
**Scale/Scope**: 2 initial profiles; extensible by dropping YAMLs in `profiles/` (FR-007)

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked post-design.*

| Principle | Status | Notes / Justification |
|-----------|--------|----------------------|
| I. Code Quality — linting enforced, single-responsibility, complexity ≤ 10, peer review | PASS | Shell scripts are minimal and single-purpose; YAML profiles are declarative; no new Python modules to lint |
| II. Testing Standards — TDD cycle, ≥ 80% unit coverage, contract tests on interface changes | PASS | E2E tests for seeded-data assertions written story-by-story; unit coverage unaffected (no new `src/` code); profile schema contract documented |
| III. UX Consistency — design system adherence, WCAG 2.1 AA, actionable error messages | N/A | No user-facing UI; failure surfaced via compose exit codes and logs — clear, actionable per spec edge cases |
| IV. Performance — latency SLA defined, performance budget in CI, profiling before optimization | PASS | Startup overhead budget defined: ≤60s increase (SC-004); noted in PR description for CI context |
| V. Simplicity — YAGNI posture, no speculative abstractions, complexity justified below | PASS | Two containers required by FR-006 (containerised generation) + FR-004 (wait-for-store); no simpler topology satisfies both; see Complexity Tracking |

---

## Project Structure

### Documentation (this feature)

```text
specs/004-pmlogsynth-integration/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── profile-schema.md   # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks — not yet created)
```

### Source Code (repository root)

```text
profiles/                          # NEW — source-controlled workload profiles
├── steady-state.yml               # NEW — baseline CPU/mem/disk/net (60 min)
└── spike.yml                      # NEW — 50-min baseline + 10-min CPU spike (60 min)

generator/                         # NEW — archive generator container build context
├── Dockerfile                     # NEW — PCP base + pip install pmlogsynth
└── entrypoint.sh                  # NEW — iterates profiles/, runs pmlogsynth for each

docker-compose.yml                 # MODIFIED — add generator, seeder, volume; add
                                   #   healthcheck to valkey; add depends_on to pcp

pyproject.toml                     # MODIFIED — pmlogsynth as optional dev dependency

tests/e2e/
├── conftest.py                    # UNCHANGED
├── test_tools.py                  # UNCHANGED (existing assertions remain valid)
└── test_seeded_data.py            # NEW — asserts spike pattern + steady-state
                                   #   data present after compose seeding
```

**Structure Decision**: Infrastructure-only additions. `src/pmmcp/` is untouched.

---

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| Two new one-shot containers (generator + seeder) | FR-006 requires containerised generation; FR-004 requires seeder to wait for valkey — these are naturally separate one-shot concerns with different dependencies | Single container doing both would couple two distinct failure modes; `pmseries --load` requires a running valkey target so ordering is required regardless |

---

## Design Decisions (post-research)

### Archive generation base image
Use `quay.io/performancecopilot/pcp:latest` for the generator. PCP Python bindings (`cpmapi`)
are a hard dependency of pmlogsynth and are pre-installed in this image. Alternative
(`python:3.11-slim` + apt PCP) is fragile across Debian releases.

### Valkey readiness gating
Use compose `healthcheck` (`redis-cli -p 6379 ping`, 5s interval, 12 retries = 60s max) +
`depends_on: condition: service_healthy`. Standard compose pattern; no custom shell loop needed.

### Seeder fail-fast
If `pmseries --load` fails for any archive, seeder exits non-zero immediately. Partial data causes
silent test gaps — a loud startup failure is easier to debug (per spec edge cases).

### E2E time window strategy
E2E tests query `-90minutes` to `now`. Profiles generate 60 minutes of data. The 30-minute buffer
tolerates non-deterministic compose startup drift. Tests assert that a spike *pattern* (value
exceeding a threshold) exists somewhere in the window — not at an exact timestamp.

### Volume teardown
`podman compose down --volumes` removes `pmmcp-archives`. Generator always overwrites on
`compose up` — clean state is guaranteed without manual cleanup.
