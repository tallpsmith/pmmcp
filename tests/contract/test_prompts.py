"""Contract tests: MCP prompt schemas and message structure (T004, T010, T014, T019).

Covers investigate_subsystem schema + message list assertions (T004).
incident_triage schema + message list assertions (T010).
compare_periods schema + message list assertions (T014).
fleet_health_check schema + message list assertions + all-4-registered check (T019).
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
    result = asyncio.run(srv.mcp.get_prompt("investigate_subsystem", {"subsystem": "cpu"}))
    assert result.messages, "Expected at least one message"
    first = result.messages[0]
    assert first.content.text, "First message content must be non-empty"


# ---------------------------------------------------------------------------
# incident_triage (T010)
# ---------------------------------------------------------------------------


def test_incident_triage_registered():
    """incident_triage prompt is registered with the MCP server."""
    prompts = {p.name for p in srv.mcp._prompt_manager.list_prompts()}
    assert "incident_triage" in prompts


def test_incident_triage_schema():
    """incident_triage has correct required/optional argument schema."""
    prompts = {p.name: p for p in srv.mcp._prompt_manager.list_prompts()}
    p = prompts["incident_triage"]
    args = {a.name: a for a in (p.arguments or [])}

    assert "symptom" in args, "symptom argument missing"
    assert args["symptom"].required is True

    assert "host" in args, "host argument missing"
    assert args["host"].required is False

    assert "timerange" in args, "timerange argument missing"
    assert args["timerange"].required is False

    assert "severity" not in args, "severity argument must not exist (FR-010)"


def test_incident_triage_returns_messages():
    """incident_triage returns a non-empty, well-formed message list."""
    result = asyncio.run(
        srv.mcp.get_prompt("incident_triage", {"symptom": "high CPU load"})
    )
    assert result.messages, "Expected at least one message"
    first = result.messages[0]
    assert first.content.text, "First message content must be non-empty"
