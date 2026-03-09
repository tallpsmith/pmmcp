"""T010 — Integration tests: pcp_fetch_timeseries."""

from __future__ import annotations

import httpx
import pytest
import respx

MOCK_BASE = "http://mock-pmproxy:44322"
TEST_SERIES = "605fc77742cd0317597291329561ac4e50c0dd12"


@pytest.mark.integration
async def test_fetch_timeseries_happy_path(mcp_session):
    """pcp_fetch_timeseries returns time-series data via the MCP protocol."""
    with respx.mock(base_url=MOCK_BASE, assert_all_called=False) as mock:
        mock.get("/series/query").mock(return_value=httpx.Response(200, json=[TEST_SERIES]))
        mock.get("/series/values").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "series": TEST_SERIES,
                        "timestamp": 1547483646.2147431,
                        "value": "42.5",
                    }
                ],
            )
        )
        mock.get("/series/labels").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "series": TEST_SERIES,
                        "labels": {"metric.name": "kernel.all.load"},
                    }
                ],
            )
        )
        mock.get("/series/instances").mock(return_value=httpx.Response(200, json=[]))

        result = await mcp_session.call_tool(
            "pcp_fetch_timeseries",
            {"names": ["kernel.all.load"], "start": "-1hour", "end": "now"},
        )

    assert not result.isError, f"Unexpected MCP error: {result}"
    text = result.content[0].text
    assert "row_count" in text or "kernel" in text
