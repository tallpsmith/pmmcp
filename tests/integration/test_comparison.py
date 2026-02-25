"""T014 — Integration test: pcp_compare_windows via MCP protocol dispatch."""

from __future__ import annotations

import httpx
import pytest
import respx

MOCK_BASE = "http://mock-pmproxy:44322"
TEST_SERIES = "605fc77742cd0317597291329561ac4e50c0dd12"


@pytest.mark.integration
async def test_compare_windows_happy_path(mcp_session):
    """pcp_compare_windows returns comparison statistics via the MCP protocol."""
    with respx.mock(base_url=MOCK_BASE, assert_all_called=False) as mock:
        mock.get("/series/query").mock(return_value=httpx.Response(200, json=[TEST_SERIES]))
        mock.get("/series/values").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "series": TEST_SERIES,
                        "timestamp": 1547483646.0,
                        "value": "42.5",
                    },
                    {
                        "series": TEST_SERIES,
                        "timestamp": 1547483706.0,
                        "value": "43.1",
                    },
                ],
            )
        )
        mock.get("/series/labels").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "series": TEST_SERIES,
                        "labels": {"metric.name": "mem.util.used"},
                    }
                ],
            )
        )
        mock.get("/series/instances").mock(return_value=httpx.Response(200, json=[]))

        result = await mcp_session.call_tool(
            "pcp_compare_windows",
            {
                "names": ["mem.util.used"],
                "window_a_start": "-2hours",
                "window_a_end": "-1hour",
                "window_b_start": "-1hour",
                "window_b_end": "now",
                "interval": "5min",
            },
        )

    assert not result.isError, f"Unexpected MCP error: {result}"
    text = result.content[0].text
    # Response is a list of comparison objects
    assert "mean" in text or "delta" in text or "window" in text or "[]" in text
