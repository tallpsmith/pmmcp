# Data Model: pmlogsynth Integration

**Date**: 2026-03-03

---

## Entities

### WorkloadProfile

A YAML file committed to `profiles/` that fully describes a synthetic performance scenario.

| Field | Type | Notes |
|-------|------|-------|
| `meta.hostname` | string | default: `synthetic-host` |
| `meta.duration` | integer (seconds) | REQUIRED |
| `meta.interval` | integer (seconds) | default: 60 |
| `meta.noise` | float [0.0, 1.0] | default: 0.0 |
| `host.profile` | string | named hardware profile, e.g. `generic-small` |
| `phases[]` | array of PhaseConfig | at least one required |

**State transitions**: None — profiles are immutable config files committed to git.

**Validation rules**:
- All phase `duration` values must be positive integers
- CPU: `user_ratio + sys_ratio + iowait_ratio ≤ 1.0`
- Memory: `used_ratio + cache_ratio ≤ 1.0`
- `transition: linear` is not valid for the first phase

---

### PerformanceArchive

Binary PCP archive files generated from a WorkloadProfile. Ephemeral — never committed.

| Attribute | Value |
|-----------|-------|
| Location | Named volume `pmmcp-archives` at path `/archives/<stem>/` |
| Naming | `<profile-stem>` (e.g., `steady-state`, `spike`) |
| Files per archive | `<name>.0` (data), `<name>.index`, `<name>.meta` |
| Lifecycle | Created by generator on each `compose up`; purged by `compose down --volumes` |

---

### Compose Services

#### pmlogsynth-generator

| Attribute | Value |
|-----------|-------|
| Base image | `quay.io/performancecopilot/pcp:latest` + pmlogsynth |
| Role | One-shot: reads all `profiles/*.yml`, runs `pmlogsynth -o /archives/<stem> <profile>` |
| Volume mount | `pmmcp-archives:/archives` (write) |
| Exit behaviour | 0 on full success; non-zero on any profile failure |
| Depends on | *(none — runs first)* |

#### pmlogsynth-seeder

| Attribute | Value |
|-----------|-------|
| Base image | `quay.io/performancecopilot/pcp:latest` |
| Role | One-shot: runs `pmseries --load /archives/<stem>` for each archive |
| Volume mount | `pmmcp-archives:/archives` (read-only) |
| Exit behaviour | 0 on full success; non-zero on first failure (all-or-nothing) |
| Depends on | `pmlogsynth-generator` (service_completed_successfully) + `valkey` (service_healthy) |

#### valkey (redis-stack) — modified

| Attribute | Value |
|-----------|-------|
| Image | `redis/redis-stack:latest` |
| Healthcheck | `redis-cli -p 6379 ping` every 5s, 12 retries (60s timeout) |
| Change | **New**: healthcheck added so seeder can gate on `service_healthy` |

#### pcp — modified

| Attribute | Value |
|-----------|-------|
| Change | **New**: `depends_on: pmlogsynth-seeder: condition: service_completed_successfully` |

---

## Volume

| Name | Type | Purpose |
|------|------|---------|
| `pmmcp-archives` | Compose-managed named volume | Transfers generated archives from generator to seeder |
