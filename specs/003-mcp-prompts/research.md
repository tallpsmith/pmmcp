# Research: MCP Prompts — Investigation Workflow Templates

**Feature**: 003-mcp-prompts
**Date**: 2026-02-27
**Status**: Complete — all unknowns resolved

---

## FastMCP Prompt API

**Decision**: Use `@mcp.prompt()` decorator with typed function signatures returning `list[dict]`.

**Findings**:

```python
@mcp.prompt()
def investigate_subsystem(
    subsystem: str,
    host: str | None = None,
    timerange: str | None = None,
    symptom: str | None = None,
) -> list[dict]:
    return [{"role": "user", "content": "..."}]
```

- Parameters with no default → `required=True` in the MCP argument schema (auto-inferred)
- Parameters with `None` default → `required=False`
- Return type `list[dict]` with `{"role": "user"|"assistant", "content": str}` — FastMCP converts to `PromptMessage(role, content=TextContent(type="text", text=...))`
- `mcp.get_prompt(name, args_dict)` is **async** and returns `GetPromptResult`
- `GetPromptResult.messages` is `list[PromptMessage]`

**Rationale**: Follows the same decorator pattern as `@mcp.tool()`. Returns plain dicts for simplicity; FastMCP handles serialisation.

**Alternatives considered**: Returning `str` (single message) — rejected because multi-phase workflows benefit from multiple message turns establishing context progressively.

---

## Unit Test Pattern

**Decision**: Expose `_*_impl(...)` functions for direct unit testing, mirroring the tool pattern.

```python
# prompts/investigate.py
def _investigate_subsystem_impl(subsystem: str, host: str | None = None, ...) -> list[dict]:
    """Pure function — testable without MCP infrastructure."""
    ...

@mcp.prompt()
def investigate_subsystem(subsystem: str, ...) -> list[dict]:
    return _investigate_subsystem_impl(subsystem, ...)
```

Unit tests call `_*_impl()` directly and assert:
- At least one message returned
- Required workflow instructions present (discovery-first, missing-tool abort, etc.)
- Correct argument values interpolated into message content

**Rationale**: Consistent with existing `tools/` pattern. Avoids needing MCP infrastructure in unit tests.

---

## Contract Test Pattern

**Decision**: Use `mcp._prompt_manager.list_prompts()` for schema tests and `asyncio.run(mcp.get_prompt(...))` for message structure tests.

```python
# tests/contract/test_prompts.py
import pmmcp.server as srv

def test_all_4_prompts_registered():
    prompts = {p.name for p in srv.mcp._prompt_manager.list_prompts()}
    assert {"investigate_subsystem", "compare_periods", "fleet_health_check", "incident_triage"} <= prompts

def test_investigate_subsystem_schema():
    prompts = {p.name: p for p in srv.mcp._prompt_manager.list_prompts()}
    p = prompts["investigate_subsystem"]
    args = {a.name: a for a in (p.arguments or [])}
    assert args["subsystem"].required is True
    assert args["host"].required is False
    assert args["timerange"].required is False
    assert args["symptom"].required is False

import asyncio
def test_investigate_subsystem_returns_messages():
    result = asyncio.run(srv.mcp.get_prompt("investigate_subsystem", {"subsystem": "cpu"}))
    assert len(result.messages) >= 1
    assert result.messages[0].content.text  # non-empty
```

**Rationale**: Mirrors `test_mcp_schemas.py` pattern. No MCP ClientSession needed for prompt tests — prompts are pure functions with no I/O.

---

## Server Registration Pattern

**Decision**: Add `import pmmcp.prompts  # noqa: E402, F401` to `server.py`, mirroring the tools import.

```python
# server.py (bottom of file)
import pmmcp.tools    # noqa: E402, F401  (existing)
import pmmcp.prompts  # noqa: E402, F401  (new)
```

`src/pmmcp/prompts/__init__.py` imports all four modules to trigger `@mcp.prompt()` registration:
```python
from pmmcp.prompts import compare, health, investigate, triage  # noqa: F401
```

**Rationale**: Same side-effect import pattern as `pmmcp/tools/__init__.py`. Keeps server.py clean.

---

## E2E Test Deferral

**Decision**: E2E tests for prompt workflows are deferred. Unit + contract tests provide full coverage of prompt structure and registration.

**Rationale**: E2E tests would require invoking a prompt through a real MCP client connected to a real pmproxy instance containing known metric data. This requires repeatable, deterministic archive data — the dependency on `pmlogger-synth` (issue #13). Without it, E2E assertions would be non-deterministic.

The in-process contract tests (prompt schema + message list structure) provide high confidence that prompts are correctly registered and well-formed without requiring live data.

**Alternatives considered**: Using the existing live pmproxy E2E container (from `002-add-integration-e2e-tests`) — rejected because prompt workflow tests need to verify the *content* of AI-driven investigations, not just tool connectivity. Live data is not deterministic enough for assertion-based tests.

---

## Agent Content Mapping

| Agent file (retiring) | Content destination | Prompt |
|----------------------|---------------------|--------|
| `agents/performance-investigator.md` | Triage workflow, subsystem hints, hierarchical sampling, metric families (CPU/mem/IO/net/proc), presentation standards | `investigate_subsystem` |
| `agents/metric-explorer.md` | Namespace hierarchy, metric semantics, exploration strategy | `investigate_subsystem` |
| `agents/performance-comparator.md` | Comparison methodology, hierarchical approach, statistical interpretation | `compare_periods` |
| `agents/performance-reporter.md` | KPI table format, presentation standards, trend classification, concern thresholds | `fleet_health_check` |

`incident_triage` is wholly new — no existing agent to retire.
