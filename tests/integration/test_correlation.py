"""Integration test: pcp_correlate_metrics via MCP protocol dispatch."""

from __future__ import annotations

import httpx
import pytest
import respx

MOCK_BASE = "http://mock-pmproxy:44322"
SERIES_CPU = "aaa0000000000000000000000000000000000001"
SERIES_DISK = "bbb0000000000000000000000000000000000002"


@pytest.mark.integration
async def test_correlate_metrics_happy_path(mcp_session):
    """pcp_correlate_metrics returns correlation data via the MCP protocol."""
    with respx.mock(base_url=MOCK_BASE, assert_all_called=False) as mock:
        mock.get("/series/query").mock(
            return_value=httpx.Response(200, json=[SERIES_CPU, SERIES_DISK])
        )
        mock.get("/series/values").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"series": SERIES_CPU, "timestamp": 1547483646.0, "value": "10.0"},
                    {"series": SERIES_CPU, "timestamp": 1547483706.0, "value": "20.0"},
                    {"series": SERIES_CPU, "timestamp": 1547483766.0, "value": "30.0"},
                    {"series": SERIES_DISK, "timestamp": 1547483646.0, "value": "1.0"},
                    {"series": SERIES_DISK, "timestamp": 1547483706.0, "value": "2.0"},
                    {"series": SERIES_DISK, "timestamp": 1547483766.0, "value": "3.0"},
                ],
            )
        )
        mock.get("/series/labels").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "series": SERIES_CPU,
                        "labels": {"metric.name": "kernel.all.cpu.user"},
                    },
                    {
                        "series": SERIES_DISK,
                        "labels": {"metric.name": "disk.all.read"},
                    },
                ],
            )
        )
        mock.get("/series/instances").mock(return_value=httpx.Response(200, json=[]))

        result = await mcp_session.call_tool(
            "pcp_correlate_metrics",
            {
                "metrics": ["kernel.all.cpu.user", "disk.all.read"],
                "start": "-1hour",
                "end": "now",
                "interval": "5min",
            },
        )

    assert not result.isError, f"Unexpected MCP error: {result}"
    text = result.content[0].text
    assert "correlations" in text or "r" in text or "strength" in text


@pytest.mark.integration
async def test_correlate_metrics_too_few_returns_error(mcp_session):
    """pcp_correlate_metrics returns error when fewer than 2 metrics given via MCP."""
    with respx.mock(base_url=MOCK_BASE, assert_all_called=False):
        result = await mcp_session.call_tool(
            "pcp_correlate_metrics",
            {
                "metrics": ["kernel.all.cpu.user"],
                "start": "-1hour",
                "end": "now",
            },
        )

    assert result.isError or "Error" in result.content[0].text
