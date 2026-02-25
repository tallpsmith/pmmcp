"""Canary integration test: confirms fixture wiring before any tool tests are written."""

from __future__ import annotations

import pytest


@pytest.mark.integration
async def test_nine_tools_registered(mcp_session):
    """Fixture is wired correctly when the server exposes exactly 9 tools."""
    result = await mcp_session.list_tools()
    tool_names = [t.name for t in result.tools]
    assert len(tool_names) == 9, f"Expected 9 tools, got {len(tool_names)}: {tool_names}"
