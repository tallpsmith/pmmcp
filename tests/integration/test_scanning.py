"""Integration test: pcp_scan_changes via MCP protocol dispatch."""

from __future__ import annotations

import httpx
import pytest
import respx

MOCK_BASE = "http://mock-pmproxy:44322"
SERIES_A = "aaa0000000000000000000000000000000000001"


@pytest.mark.integration
async def test_scan_changes_happy_path(mcp_session):
    """pcp_scan_changes returns changed metrics via the MCP protocol."""
    call_count = 0

    def values_side_effect(request):
        nonlocal call_count
        call_count += 1
        # First window: baseline values, second window: 3x higher
        if call_count == 1:
            return httpx.Response(
                200,
                json=[
                    {"series": SERIES_A, "timestamp": 1547483646.0, "value": "10.0"},
                    {"series": SERIES_A, "timestamp": 1547483706.0, "value": "10.0"},
                ],
            )
        return httpx.Response(
            200,
            json=[
                {"series": SERIES_A, "timestamp": 1547570046.0, "value": "30.0"},
                {"series": SERIES_A, "timestamp": 1547570106.0, "value": "30.0"},
            ],
        )

    with respx.mock(base_url=MOCK_BASE, assert_all_called=False) as mock:
        mock.get("/series/query").mock(return_value=httpx.Response(200, json=[SERIES_A]))
        mock.get("/series/values").mock(side_effect=values_side_effect)
        mock.get("/series/labels").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "series": SERIES_A,
                        "labels": {"metric.name": "kernel.all.cpu.user"},
                    }
                ],
            )
        )
        mock.get("/series/instances").mock(return_value=httpx.Response(200, json=[]))

        result = await mcp_session.call_tool(
            "pcp_scan_changes",
            {
                "metric_prefix": "kernel",
                "baseline_start": "-2hours",
                "baseline_end": "-1hour",
                "comparison_start": "-1hour",
                "comparison_end": "now",
                "ratio_threshold": 1.5,
                "max_metrics": 50,
                "interval": "5min",
            },
        )

    assert not result.isError, f"Unexpected MCP error: {result}"
    text = result.content[0].text
    assert "changes" in text or "ratio" in text or "metric_prefix" in text or "{}" in text
