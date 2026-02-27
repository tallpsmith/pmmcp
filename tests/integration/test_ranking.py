"""Integration test: pcp_rank_hosts via MCP protocol dispatch."""

from __future__ import annotations

import httpx
import pytest
import respx

MOCK_BASE = "http://mock-pmproxy:44322"
SERIES_A = "aaa0000000000000000000000000000000000001"
SERIES_B = "bbb0000000000000000000000000000000000002"


@pytest.mark.integration
async def test_rank_hosts_happy_path(mcp_session):
    """pcp_rank_hosts returns host ranking statistics via the MCP protocol."""
    with respx.mock(base_url=MOCK_BASE, assert_all_called=False) as mock:
        mock.get("/series/query").mock(return_value=httpx.Response(200, json=[SERIES_A, SERIES_B]))
        mock.get("/series/values").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"series": SERIES_A, "timestamp": 1547483646.0, "value": "80.0"},
                    {"series": SERIES_A, "timestamp": 1547483706.0, "value": "82.0"},
                    {"series": SERIES_B, "timestamp": 1547483646.0, "value": "20.0"},
                    {"series": SERIES_B, "timestamp": 1547483706.0, "value": "22.0"},
                ],
            )
        )
        mock.get("/series/labels").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "series": SERIES_A,
                        "labels": {
                            "metric.name": "kernel.all.cpu.user",
                            "hostname": "host-a",
                        },
                    },
                    {
                        "series": SERIES_B,
                        "labels": {
                            "metric.name": "kernel.all.cpu.user",
                            "hostname": "host-b",
                        },
                    },
                ],
            )
        )

        result = await mcp_session.call_tool(
            "pcp_rank_hosts",
            {
                "metric": "kernel.all.cpu.user",
                "start": "-1hour",
                "end": "now",
                "criterion": "mean",
                "interval": "5min",
            },
        )

    assert not result.isError, f"Unexpected MCP error: {result}"
    text = result.content[0].text
    assert "host" in text or "cluster" in text or "metric" in text


@pytest.mark.integration
async def test_rank_hosts_invalid_criterion_returns_error(mcp_session):
    """pcp_rank_hosts returns an error for invalid criterion via MCP."""
    with respx.mock(base_url=MOCK_BASE, assert_all_called=False):
        result = await mcp_session.call_tool(
            "pcp_rank_hosts",
            {
                "metric": "kernel.all.cpu.user",
                "start": "-1hour",
                "end": "now",
                "criterion": "median",
            },
        )

    assert result.isError or "Error" in result.content[0].text
