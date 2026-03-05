# Quickstart: pcp_quick_investigate

**Feature**: 006-quick-investigate | **Date**: 2026-03-05

## Dev Setup

```bash
# Ensure deps are current (idempotent, fast)
uv sync --extra dev
```

## Implementation Order

### Story 1: Core tool with smart defaults (P1)

```bash
# 1. Write failing tests
# tests/unit/test_investigate.py — test _quick_investigate_impl with mocked client
uv run pytest tests/unit/test_investigate.py  # RED

# 2. Implement
# src/pmmcp/tools/investigate.py — _quick_investigate_impl + @mcp.tool wrapper
# src/pmmcp/tools/__init__.py — add investigate import
uv run pytest tests/unit/test_investigate.py  # GREEN

# 3. Sanity check
scripts/pre-push-sanity.sh
```

### Story 2: Tool description updates (P2)

```bash
# 1. Write contract tests verifying description content
uv run pytest tests/contract/  # RED

# 2. Update descriptions in anomaly.py, comparison.py, scanning.py, timeseries.py
uv run pytest tests/contract/  # GREEN

scripts/pre-push-sanity.sh
```

### Story 3: Prompt update (P2)

```bash
# 1. Write test for updated prompt content
uv run pytest tests/unit/test_prompts.py  # RED (or contract tests)

# 2. Update prompts/investigate.py
uv run pytest tests/unit/test_prompts.py  # GREEN

scripts/pre-push-sanity.sh
```

### Story 4: Optional scope parameters (P3)

```bash
# 1. Write tests for subsystem, lookback, baseline_days parameters
uv run pytest tests/unit/test_investigate.py  # RED

# 2. Implement parameter handling in _quick_investigate_impl
uv run pytest tests/unit/test_investigate.py  # GREEN

scripts/pre-push-sanity.sh
```

## Key Files

| File | Action | Purpose |
|------|--------|---------|
| `src/pmmcp/tools/investigate.py` | CREATE | New tool: `pcp_quick_investigate` |
| `src/pmmcp/tools/__init__.py` | EDIT | Register new module |
| `src/pmmcp/tools/anomaly.py` | EDIT | Update tool description |
| `src/pmmcp/tools/comparison.py` | EDIT | Update tool description |
| `src/pmmcp/tools/scanning.py` | EDIT | Update tool description |
| `src/pmmcp/tools/timeseries.py` | EDIT | Update tool description |
| `src/pmmcp/prompts/investigate.py` | EDIT | Update prompt guidance |
| `tests/unit/test_investigate.py` | CREATE | Unit tests |
| `tests/contract/test_tool_registration.py` | EDIT | Contract test for new tool |

## Verification

```bash
# Full test suite with coverage
uv run pytest --cov=pmmcp --cov-report=term-missing

# Lint + format
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/

# Pre-push sanity (all of the above)
scripts/pre-push-sanity.sh
```

## E2E Smoke Test (optional, requires pmproxy)

```bash
PMPROXY_URL=http://localhost:44322 uv run pytest -m e2e -k investigate
```
