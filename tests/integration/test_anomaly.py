"""Integration test: pcp_detect_anomalies via MCP protocol dispatch."""

from __future__ import annotations

import httpx
import pytest
import respx

MOCK_BASE = "http://mock-pmproxy:44322"
TEST_SERIES = "605fc77742cd0317597291329561ac4e50c0dd12"


@pytest.mark.integration
async def test_detect_anomalies_happy_path(mcp_session):
    """pcp_detect_anomalies returns anomaly data via the MCP protocol."""
    with respx.mock(base_url=MOCK_BASE, assert_all_called=False) as mock:
        mock.get("/series/query").mock(return_value=httpx.Response(200, json=[TEST_SERIES]))
        mock.get("/series/values").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"series": TEST_SERIES, "timestamp": 1547483646.0, "value": "10.0"},
                    {"series": TEST_SERIES, "timestamp": 1547483706.0, "value": "11.0"},
                    {"series": TEST_SERIES, "timestamp": 1547483766.0, "value": "10.5"},
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
            "pcp_detect_anomalies",
            {
                "metrics": ["mem.util.used"],
                "recent_start": "-15min",
                "recent_end": "now",
                "baseline_start": "-6hours",
                "baseline_end": "-15min",
                "z_score_threshold": 2.0,
            },
        )

    assert not result.isError, f"Unexpected MCP error: {result}"
    text = result.content[0].text
    assert "severity" in text or "baseline" in text or "z_score" in text or "[]" in text
