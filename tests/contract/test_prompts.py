"""Contract tests: MCP prompt schemas and message structure (T004).

Covers investigate_subsystem schema + message list assertions.
Additional prompts (incident_triage, compare_periods, fleet_health_check)
will be added in subsequent stories.
"""

from __future__ import annotations

import asyncio

import pmmcp.server as srv


def test_investigate_subsystem_registered():
    """investigate_subsystem prompt is registered with the MCP server."""
    prompts = {p.name for p in srv.mcp._prompt_manager.list_prompts()}
    assert "investigate_subsystem" in prompts


def test_investigate_subsystem_schema():
    """investigate_subsystem has correct required/optional argument schema."""
    prompts = {p.name: p for p in srv.mcp._prompt_manager.list_prompts()}
    p = prompts["investigate_subsystem"]
    args = {a.name: a for a in (p.arguments or [])}

    assert "subsystem" in args, "subsystem argument missing"
    assert args["subsystem"].required is True

    assert "host" in args, "host argument missing"
    assert args["host"].required is False

    assert "timerange" in args, "timerange argument missing"
    assert args["timerange"].required is False

    assert "symptom" in args, "symptom argument missing"
    assert args["symptom"].required is False


def test_investigate_subsystem_returns_messages():
    """investigate_subsystem returns a non-empty, well-formed message list."""
    result = asyncio.run(
        srv.mcp.get_prompt("investigate_subsystem", {"subsystem": "cpu"})
    )
    assert result.messages, "Expected at least one message"
    first = result.messages[0]
    assert first.content.text, "First message content must be non-empty"
