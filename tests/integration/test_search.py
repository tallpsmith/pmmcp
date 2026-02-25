"""T011 — Integration test: pcp_search via MCP protocol dispatch."""

from __future__ import annotations

import httpx
import pytest
import respx

MOCK_BASE = "http://mock-pmproxy:44322"


@pytest.mark.integration
async def test_search_happy_path(mcp_session):
    """pcp_search returns ranked metric results via the MCP protocol."""
    with respx.mock(base_url=MOCK_BASE, assert_all_called=False) as mock:
        mock.get("/search/text").mock(
            return_value=httpx.Response(
                200,
                json={
                    "total": 1,
                    "elapsed": 0.001,
                    "offset": 0,
                    "limit": 20,
                    "results": [
                        {
                            "name": "kernel.all.load",
                            "type": "metric",
                            "oneline": "1, 5 and 15 minute load average",
                            "helptext": "Extended help text",
                            "score": 1.0,
                        }
                    ],
                },
            )
        )

        result = await mcp_session.call_tool("pcp_search", {"query": "kernel"})

    assert not result.isError, f"Unexpected MCP error: {result}"
    text = result.content[0].text
    assert "kernel" in text
