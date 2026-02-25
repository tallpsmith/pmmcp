"""T008 — Integration test: pcp_get_hosts via MCP protocol dispatch."""

from __future__ import annotations

import httpx
import pytest
import respx

MOCK_BASE = "http://mock-pmproxy:44322"
TEST_SOURCE = "2cd6a38f9339f2dd1f0b4775bda89a9e7244def6"


@pytest.mark.integration
async def test_get_hosts_happy_path(mcp_session):
    """pcp_get_hosts returns a paginated host list via the MCP protocol."""
    with respx.mock(base_url=MOCK_BASE, assert_all_called=False) as mock:
        mock.get("/series/sources").mock(return_value=httpx.Response(200, json=[TEST_SOURCE]))
        mock.get("/series/labels").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "series": TEST_SOURCE,
                        "labels": {"hostname": "localhost", "agent": "linux"},
                    }
                ],
            )
        )

        result = await mcp_session.call_tool("pcp_get_hosts", {})

    assert not result.isError, f"Unexpected MCP error: {result}"
    text = result.content[0].text
    assert "hosts" in text.lower() or "localhost" in text
