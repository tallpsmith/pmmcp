"""T009 — Integration test: pcp_fetch_live via MCP protocol dispatch."""

from __future__ import annotations

import httpx
import pytest
import respx

MOCK_BASE = "http://mock-pmproxy:44322"
TEST_CONTEXT = 348734


@pytest.mark.integration
async def test_fetch_live_happy_path(mcp_session):
    """pcp_fetch_live returns live metric values via the MCP protocol."""
    with respx.mock(base_url=MOCK_BASE, assert_all_called=False) as mock:
        mock.get("/pmapi/context").mock(
            return_value=httpx.Response(
                200, json={"context": TEST_CONTEXT, "hostspec": "localhost", "labels": {}}
            )
        )
        mock.get("/pmapi/indom").mock(
            return_value=httpx.Response(
                200,
                json={
                    "context": TEST_CONTEXT,
                    "indom": "60.2",
                    "instances": [
                        {"instance": 1, "name": "1 minute"},
                        {"instance": 5, "name": "5 minute"},
                        {"instance": 15, "name": "15 minute"},
                    ],
                },
            )
        )
        mock.get("/pmapi/fetch").mock(
            return_value=httpx.Response(
                200,
                json={
                    "context": TEST_CONTEXT,
                    "timestamp": 1547483646.2147431,
                    "values": [
                        {
                            "pmid": "60.0.4",
                            "name": "kernel.all.load",
                            "instances": [
                                {"instance": 1, "value": 0.1},
                                {"instance": 5, "value": 0.25},
                                {"instance": 15, "value": 0.17},
                            ],
                        }
                    ],
                },
            )
        )

        result = await mcp_session.call_tool("pcp_fetch_live", {"names": ["kernel.all.load"]})

    assert not result.isError, f"Unexpected MCP error: {result}"
    text = result.content[0].text
    assert "kernel" in text or "0.1" in text or "values" in text
