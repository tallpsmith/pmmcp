# Quickstart: pmlogsynth Integration

**Date**: 2026-03-03

---

## Running the Full Stack with Seeded Data

```bash
# Start all services
# Generator runs first → seeder loads data → pcp/pmproxy starts last
podman compose up -d

# Watch seeding progress (optional)
podman compose logs -f pmlogsynth-generator pmlogsynth-seeder

# Run E2E tests against seeded data
PMPROXY_URL=http://localhost:44322 uv run pytest tests/e2e/ -m e2e -v

# Tear down and purge all data (including archives volume)
podman compose down --volumes
```

---

## Adding a New Profile

1. Create `profiles/<name>.yml` following the [profile schema](contracts/profile-schema.md)
2. Validate locally (requires Linux with PCP installed):
   ```bash
   uv run pmlogsynth --validate profiles/<name>.yml
   ```
3. Restart the stack:
   ```bash
   podman compose down --volumes && podman compose up -d
   ```
4. The new profile's data is immediately queryable — no other changes needed.

---

## Debugging Failures

```bash
# Check what went wrong in generator or seeder
podman compose logs pmlogsynth-generator
podman compose logs pmlogsynth-seeder

# Inspect what archives were actually written to the shared volume
podman run --rm \
  -v pmmcp_pmmcp-archives:/archives:ro \
  quay.io/performancecopilot/pcp:latest \
  ls -lh /archives/
```

---

## Installing pmlogsynth Locally (Linux only)

Profile authors on Linux machines with PCP installed can install pmlogsynth for local validation:

```bash
uv sync --extra dev
uv run pmlogsynth --validate profiles/steady-state.yml
```

On macOS the package installs but import fails without system PCP — use the Linux VM instead.
