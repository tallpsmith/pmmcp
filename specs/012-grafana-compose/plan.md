# Implementation Plan: Grafana & mcp-grafana Compose Integration

**Branch**: `012-grafana-compose` | **Date**: 2026-03-10 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/012-grafana-compose/spec.md`

## Summary

Add Grafana (with auto-provisioned PCP datasources) and mcp-grafana to the existing docker-compose stack, enabling local visualisation and the foundation for Issue #10's prompt-driven Grafana integration. No new Python code — purely infrastructure (compose services, provisioning files, CI updates).

## Technical Context

**Language/Version**: N/A (infrastructure-only; compose YAML, Grafana provisioning YAML)
**Primary Dependencies**: `grafana/grafana:latest`, `mcp/grafana` (Docker Hub), `performancecopilot-pcp-app` plugin v5.3.0
**Storage**: Ephemeral — no persistent volumes for Grafana
**Testing**: E2E smoke tests (curl-based healthchecks + datasource verification); existing pytest E2E suite must not regress
**Target Platform**: podman compose (local) + docker compose (CI, GitHub Actions)
**Project Type**: single (infrastructure addition to existing compose stack)
**Performance Goals**: All services healthy within 90 seconds of `compose up`
**Constraints**: Plugin is unsigned (requires `GF_PLUGINS_ALLOW_LOADING_UNSIGNED_PLUGINS`); mcp-grafana requires auth (basic auth with `admin/admin`)
**Scale/Scope**: 2 new compose services, 1 provisioning file, CI workflow update

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes / Justification |
|-----------|--------|----------------------|
| I. Code Quality — linting enforced, single-responsibility, complexity ≤ 10, peer review, documentation impact reviewed | PASS | No new Python code. Compose YAML and provisioning YAML are declarative. Documentation (README, CLAUDE.md, docker-compose.yml comments) will be updated in the same PR. |
| II. Testing Standards — TDD cycle, ≥ 80% unit coverage, contract tests on interface changes | PASS | No new Python code means no unit coverage impact. E2E smoke tests verify service health. Existing E2E tests must not regress (SC-005). TDD applies to any new pytest fixtures if added. |
| III. UX Consistency — design system adherence, WCAG 2.1 AA, actionable error messages | N/A | No user-facing UI changes. Grafana provides its own UX. |
| IV. Performance — latency SLA defined, performance budget in CI, profiling before optimization | PASS | SC-001 defines 90-second startup SLA. No runtime performance impact on pmmcp — Grafana and mcp-grafana are independent services. |
| V. Simplicity — YAGNI posture, no speculative abstractions, complexity justified below | PASS | Minimal additions: 2 services in compose, 1 provisioning file. No custom images, no init containers, no token bootstrapping — basic auth is the simplest working path. |

## Project Structure

### Documentation (this feature)

```text
specs/012-grafana-compose/
├── plan.md              # This file
├── research.md          # Phase 0: mcp-grafana, PCP plugin, auth, CI research
├── data-model.md        # Service topology and configuration relationships
├── quickstart.md        # Developer quickstart for the Grafana stack
├── contracts/
│   └── compose-services.md  # Service definitions, env vars, dependency chain
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
docker-compose.yml                          # Modified: add grafana + mcp-grafana services
grafana/
└── provisioning/
    └── datasources/
        └── pcp.yaml                        # New: auto-provision PCP Valkey + Vector datasources
.github/workflows/ci.yml                    # Modified: add Grafana wait step in E2E job
```

**Structure Decision**: No new Python source files. The feature is entirely compose infrastructure + Grafana provisioning configuration. The only code changes are to `docker-compose.yml` and `.github/workflows/ci.yml`.
