# Research: pmlogsynth Integration

**Date**: 2026-03-03

---

## 1. pmlogsynth Installation

**Decision**: Install from `git+https://github.com/tallpsmith/pmlogsynth` in the generator
container Dockerfile; add as optional dev dependency in `pyproject.toml`.

**Rationale**: No PyPI release exists. The spec (FR-009) explicitly allows `@main` tracking
until tagged releases exist.

**Install command**:
```
pip install git+https://github.com/tallpsmith/pmlogsynth
```

**macOS caveat**: PCP Python bindings (`cpmapi`) require system PCP installed. macOS developers
running the stack via a Linux VM (per existing project setup) need not install pmlogsynth locally.
The spec Assumptions explicitly call this out as acceptable.

**Alternatives considered**: Vendoring the source — rejected; breaks upgrade path.

---

## 2. Profile YAML Schema

**Decision**: Follow the pmlogsynth native schema — `meta`, `host`, `phases` sections. No custom
format translation (spec Assumption 3).

**Schema summary**:

| Section | Key fields |
|---------|-----------|
| `meta` | `hostname`, `timezone`, `duration` (secs), `interval` (secs), `noise` |
| `host` | `profile: <name>` or inline `cpus`, `memory_kb`, `disks`, `interfaces` |
| `phases` | array of `{name, duration, transition, cpu, memory, disk, network}` |

**Stressor ranges**:
- `cpu.utilization` [0.0, 1.0]; `user_ratio + sys_ratio + iowait_ratio ≤ 1.0`
- `memory.used_ratio` [0.0, 1.0]; `used_ratio + cache_ratio ≤ 1.0`
- `disk.read_mbps` / `write_mbps` floats
- `network.rx_mbps` / `tx_mbps` floats

**Transition types**: `instant` (default) or `linear` (not valid for first phase).

---

## 3. Container Architecture

**Decision**: Two one-shot containers with `depends_on` ordering in compose.

```
pmlogsynth-generator (one-shot)
  → writes archives to named volume pmmcp-archives
  → exits 0 on success, non-zero on any failure (fail-fast)

pmlogsynth-seeder (one-shot)
  depends_on: pmlogsynth-generator (condition: service_completed_successfully)
  depends_on: valkey (condition: service_healthy)
  → reads archives from named volume
  → runs pmseries --load <archive> for each
  → exits non-zero on first failure (all-or-nothing, per spec edge cases)

pcp (long-running)
  depends_on: pmlogsynth-seeder (condition: service_completed_successfully)
```

**Alternatives considered**:
- Single container doing generate + seed: Rejected — couples two distinct failure modes; pmseries
  requires a running store so ordering is non-trivial regardless.
- Host-side generation script: Rejected — violates FR-006 (must run entirely in a container).

---

## 4. Valkey Readiness Wait

**Decision**: Use compose `healthcheck` on the valkey service (`redis-cli -p 6379 ping`) +
`depends_on: condition: service_healthy` on the seeder.

**Rationale**: Standard compose pattern — no custom wait-loop scripting in the seeder.

**Healthcheck configuration**:
```yaml
healthcheck:
  test: ["CMD", "redis-cli", "-p", "6379", "ping"]
  interval: 5s
  timeout: 3s
  retries: 12   # 60 seconds maximum — matches spec requirement
```

**Alternatives considered**: Custom shell loop with `redis-cli ping` in the seeder — more fragile
than compose healthcheck; rejected.

---

## 5. Archive Volume Lifecycle

**Decision**: Named volume `pmmcp-archives` shared between generator and seeder. Teardown uses
`podman compose down --volumes`.

**Rationale**: Named volumes survive `podman compose stop` within a session; `down --volumes`
purges them. Generator always overwrites on `compose up` — clean state guaranteed.

**Alternatives considered**: Bind-mount to host path — introduces host filesystem side effects;
rejected.

---

## 6. Generator Base Image

**Decision**: Use `quay.io/performancecopilot/pcp:latest` as the base for the generator container.

**Rationale**: PCP Python bindings (`cpmapi`, `pcp` module) are a hard dependency of pmlogsynth.
Pre-installed in the PCP base image — no apt/dnf dependency resolution required at build time.

**Dockerfile install step**:
```dockerfile
RUN pip install git+https://github.com/tallpsmith/pmlogsynth
```

**Alternatives considered**: `python:3.11-slim` + `apt-get install pcp` — fragile; PCP apt
packaging availability varies across Debian versions; rejected.

---

## 7. Initial Profiles

**Decision**: Two profiles:
1. `steady-state.yml` — 60 min: CPU ~30%, memory ~60%, disk moderate, network moderate
2. `spike.yml` — 60 min: 50-min baseline then 10-min CPU spike to ~90% + memory pressure

**Rationale**: FR-008 requires at minimum steady-state and anomaly/spike profiles. 60-minute
duration ensures E2E queries with `-90minutes` window (per spec's wide-window strategy) always
capture all data regardless of compose startup drift.

**E2E test strategy**: Tests query with `-90minutes` to `now`. Assert that a spike pattern
(cpu_utilization > 0.85) exists somewhere in the returned series. No exact timestamp assertions —
intentionally testing fuzzy pattern-finding per spec clarification.

---

## 8. pmlogsynth as Dev Dependency

**Decision**: Add to `pyproject.toml` under `[project.optional-dependencies]` `dev` group as:
```
pmlogsynth @ git+https://github.com/tallpsmith/pmlogsynth
```

**Rationale**: FR-009. Enables profile authors on Linux machines with PCP installed to validate
profiles locally before committing.

**macOS**: Package installs but import fails without system PCP. Acceptable per spec Assumptions.
