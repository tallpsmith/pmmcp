"""Canary integration test: confirms fixture wiring before any tool tests are written."""

from __future__ import annotations

import pytest


@pytest.mark.integration
async def test_tools_registered(mcp_session):
    """Fixture is wired correctly when the server exposes the expected tools."""
    result = await mcp_session.list_tools()
    tool_names = [t.name for t in result.tools]
    assert len(tool_names) == 13, f"Expected 13 tools, got {len(tool_names)}: {tool_names}"
