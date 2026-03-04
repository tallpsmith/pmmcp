# Contract: Profile YAML Schema

**Date**: 2026-03-03

This document defines the schema for workload profile YAML files stored in `profiles/`.
These files are the developer-facing interface to the pmlogsynth archive generator.

---

## Full Schema

```yaml
meta:
  hostname: string          # default: "synthetic-host"
  timezone: string          # default: "UTC"; must be a valid tz string
  duration: integer         # REQUIRED; total seconds (sum of all phase durations)
  interval: integer         # default: 60; seconds between samples
  noise: float              # [0.0, 1.0]; default: 0.0; global noise floor

host:
  profile: string           # named hardware profile, e.g. "generic-small", "generic-large"
  # OR inline:
  name: string
  cpus: integer
  memory_kb: integer
  disks:
    - name: string
      type: string           # e.g. "ssd", "hdd"
  interfaces:
    - name: string
      speed_mbps: float

phases:
  - name: string            # REQUIRED; unique within the profile
    duration: integer       # REQUIRED; seconds
    transition: string      # "instant" (default) or "linear" (not valid for first phase)
    cpu:
      utilization: float    # [0.0, 1.0]; overall CPU busy fraction
      user_ratio: float     # default: 0.70; fraction of utilization in user mode
      sys_ratio: float      # default: 0.20; fraction of utilization in kernel mode
      iowait_ratio: float   # default: 0.10; fraction in iowait
      noise: float          # [0.0, 1.0]; overrides meta.noise for this stressor
    memory:
      used_ratio: float     # [0.0, 1.0]; fraction of total memory in use
      cache_ratio: float    # [0.0, 1.0]; fraction of total memory as page cache
      noise: float
    disk:
      read_mbps: float      # default: 0.0
      write_mbps: float     # default: 0.0
      iops_read: integer    # derived from read_mbps if omitted
      iops_write: integer   # derived from write_mbps if omitted
      noise: float
    network:
      rx_mbps: float        # default: 0.0
      tx_mbps: float        # default: 0.0
      noise: float
```

---

## Constraints

| Rule | Applies to |
|------|-----------|
| `user_ratio + sys_ratio + iowait_ratio ≤ 1.0` | Every phase with a `cpu` stressor |
| `used_ratio + cache_ratio ≤ 1.0` | Every phase with a `memory` stressor |
| `transition: linear` not valid for the first phase | First element of `phases[]` |
| `meta.duration` must equal the sum of all phase `duration` values (unless `repeat` is used) | Top level |

---

## Validation

```bash
# Requires PCP Python bindings (Linux only)
uv run pmlogsynth --validate profiles/<name>.yml
```

---

## Produced Metrics

pmlogsynth produces 24 PCP metrics. Key ones used in E2E assertions:

| PCP Metric | Stressor |
|------------|---------|
| `kernel.all.cpu.user` | cpu |
| `kernel.all.cpu.sys` | cpu |
| `kernel.all.cpu.wait.total` | cpu |
| `mem.util.used` | memory |
| `mem.util.cached` | memory |
| `mem.physmem` | memory |
| `disk.all.read` | disk |
| `disk.all.write` | disk |
| `disk.all.read_bytes` | disk |
| `disk.all.write_bytes` | disk |
| `network.interface.in.bytes` | network |
| `network.interface.out.bytes` | network |
