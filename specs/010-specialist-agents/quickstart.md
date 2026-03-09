# Quickstart: Specialist Agent Investigation Coordinator

## What Changed

1. **New prompt**: `specialist_investigate(subsystem, ...)` — deep domain expertise per subsystem
2. **New prompt**: `coordinate_investigation(request, ...)` — parallel dispatch of 6 specialists + synthesis
3. **Tweak**: `pcp_search` default limit 20→50
4. **Update**: `session_init` references coordinator as investigation entry point

## Quick Test

```bash
# Run all tests
uv sync --extra dev
uv run pytest --cov=pmmcp --cov-report=term-missing

# Run just the new prompt tests
uv run pytest tests/unit/test_prompts_specialist.py tests/unit/test_prompts_coordinator.py -v

# Run contract tests
uv run pytest tests/contract/test_prompts.py -v
```

## Usage

### Coordinator (primary entry point)
Invoke the `coordinate_investigation` prompt:
- `request`: "the app is slow" (required)
- `host`: target host (optional)
- `time_of_interest`: "now" (default)
- `lookback`: "2hours" (default)

The coordinator instructs the LLM to dispatch all 6 specialists concurrently (or sequentially if sub-agents aren't supported), then synthesise findings.

### Individual Specialist
Invoke `specialist_investigate` directly:
- `subsystem`: one of cpu, memory, disk, network, process, crosscutting
- Same optional args as coordinator

Each specialist carries deep domain knowledge — not just namespace hints.
