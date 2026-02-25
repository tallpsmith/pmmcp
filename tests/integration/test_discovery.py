"""T012 — Integration tests: pcp_discover_metrics and pcp_get_metric_info."""

from __future__ import annotations

import httpx
import pytest
import respx

MOCK_BASE = "http://mock-pmproxy:44322"
TEST_CONTEXT = 348734
TEST_SERIES = "605fc77742cd0317597291329561ac4e50c0dd12"
TEST_SOURCE = "2cd6a38f9339f2dd1f0b4775bda89a9e7244def6"


@pytest.mark.integration
async def test_discover_metrics_prefix_mode(mcp_session):
    """pcp_discover_metrics (prefix) browses the namespace tree via the MCP protocol."""
    with respx.mock(base_url=MOCK_BASE, assert_all_called=False) as mock:
        mock.get("/pmapi/context").mock(
            return_value=httpx.Response(
                200, json={"context": TEST_CONTEXT, "hostspec": "localhost", "labels": {}}
            )
        )
        mock.get("/pmapi/children").mock(
            return_value=httpx.Response(
                200,
                json={
                    "context": TEST_CONTEXT,
                    "name": "kernel",
                    "leaf": ["uname"],
                    "nonleaf": ["all", "percpu"],
                },
            )
        )

        result = await mcp_session.call_tool("pcp_discover_metrics", {"prefix": "kernel"})

    assert not result.isError, f"Unexpected MCP error: {result}"
    text = result.content[0].text
    assert "items" in text or "kernel" in text


@pytest.mark.integration
async def test_discover_metrics_search_mode(mcp_session):
    """pcp_discover_metrics (search) calls RediSearch via the MCP protocol."""
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
                        }
                    ],
                },
            )
        )

        result = await mcp_session.call_tool("pcp_discover_metrics", {"search": "load average"})

    assert not result.isError, f"Unexpected MCP error: {result}"
    text = result.content[0].text
    assert "kernel" in text or "items" in text


@pytest.mark.integration
async def test_get_metric_info_happy_path(mcp_session):
    """pcp_get_metric_info returns metadata fields via the MCP protocol."""
    with respx.mock(base_url=MOCK_BASE, assert_all_called=False) as mock:
        mock.get("/pmapi/context").mock(
            return_value=httpx.Response(
                200, json={"context": TEST_CONTEXT, "hostspec": "localhost", "labels": {}}
            )
        )
        mock.get("/pmapi/metric").mock(
            return_value=httpx.Response(
                200,
                json={
                    "context": TEST_CONTEXT,
                    "metrics": [
                        {
                            "name": "kernel.all.load",
                            "pmid": "60.2.0",
                            "indom": "60.2",
                            "type": "FLOAT",
                            "sem": "instant",
                            "units": "none",
                            "series": TEST_SERIES,
                            "source": TEST_SOURCE,
                            "labels": {"hostname": "localhost"},
                            "text-oneline": "1, 5 and 15 minute load average",
                            "text-help": "Extended help text",
                        }
                    ],
                },
            )
        )
        mock.get("/pmapi/indom").mock(
            return_value=httpx.Response(
                200,
                json={
                    "context": TEST_CONTEXT,
                    "indom": "60.2",
                    "labels": {},
                    "instances": [
                        {"instance": 1, "name": "1 minute", "labels": {}},
                        {"instance": 5, "name": "5 minute", "labels": {}},
                        {"instance": 15, "name": "15 minute", "labels": {}},
                    ],
                },
            )
        )

        result = await mcp_session.call_tool("pcp_get_metric_info", {"names": ["kernel.all.load"]})

    assert not result.isError, f"Unexpected MCP error: {result}"
    text = result.content[0].text
    assert "kernel.all.load" in text or "pmid" in text or "FLOAT" in text
