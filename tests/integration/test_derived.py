"""T013 — Integration test: pcp_derive_metric via MCP protocol dispatch."""

from __future__ import annotations

import httpx
import pytest
import respx

MOCK_BASE = "http://mock-pmproxy:44322"
TEST_CONTEXT = 348734


@pytest.mark.integration
async def test_derive_metric_happy_path(mcp_session):
    """pcp_derive_metric registers a derived metric via the MCP protocol."""
    with respx.mock(base_url=MOCK_BASE, assert_all_called=False) as mock:
        mock.get("/pmapi/context").mock(
            return_value=httpx.Response(
                200, json={"context": TEST_CONTEXT, "hostspec": "localhost", "labels": {}}
            )
        )
        mock.get("/pmapi/derive").mock(
            return_value=httpx.Response(200, json={"context": TEST_CONTEXT, "success": True})
        )

        result = await mcp_session.call_tool(
            "pcp_derive_metric",
            {
                "name": "test.derived.load",
                "expr": "kernel.all.load",
            },
        )

    assert not result.isError, f"Unexpected MCP error: {result}"
    text = result.content[0].text
    assert "success" in text or "test.derived.load" in text
