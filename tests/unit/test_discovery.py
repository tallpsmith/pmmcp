"""Tests for pcp_discover_metrics and pcp_get_metric_info tools (T029)."""

from __future__ import annotations

import httpx
import pytest
import respx

from pmmcp.client import PmproxyClient
from pmmcp.config import PmproxyConfig

PMPROXY_BASE = "http://localhost:44322"
TEST_CONTEXT = 348734
TEST_SERIES = "605fc77742cd0317597291329561ac4e50c0dd12"
TEST_SOURCE = "2cd6a38f9339f2dd1f0b4775bda89a9e7244def6"


@pytest.fixture
def config():
    return PmproxyConfig(url=PMPROXY_BASE, timeout=5.0)


def _mock_context():
    return httpx.Response(
        200, json={"context": TEST_CONTEXT, "hostspec": "localhost", "labels": {}}
    )


@respx.mock
async def test_discover_metrics_prefix_uses_children(config):
    """pcp_discover_metrics(prefix) uses /pmapi/children endpoint."""
    respx.get(f"{PMPROXY_BASE}/pmapi/context").mock(return_value=_mock_context())
    respx.get(f"{PMPROXY_BASE}/pmapi/children").mock(
        return_value=httpx.Response(
            200,
            json={
                "context": TEST_CONTEXT,
                "name": "kernel",
                "leaf": ["nprocs", "uname"],
                "nonleaf": ["percpu", "all"],
            },
        )
    )

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.discovery import _discover_metrics_impl

        result = await _discover_metrics_impl(
            client, host="", prefix="kernel", search="", limit=50, offset=0
        )
        assert not result.get("isError"), f"Got error: {result}"
        assert "items" in result
        names = [item["name"] for item in result["items"]]
        # Should contain both leaf and nonleaf children
        assert any("nprocs" in n or "kernel.nprocs" in n for n in names)
        # Leaf items should have leaf=True
        leaf_items = [item for item in result["items"] if item.get("leaf") is True]
        assert len(leaf_items) > 0
    finally:
        await client.close()


@respx.mock
async def test_discover_metrics_search_uses_search_endpoint(config):
    """pcp_discover_metrics(search) uses /search/text endpoint."""
    search_route = respx.get(f"{PMPROXY_BASE}/search/text").mock(
        return_value=httpx.Response(
            200,
            json={
                "total": 1,
                "elapsed": 0.001,
                "offset": 0,
                "limit": 50,
                "results": [
                    {
                        "name": "kernel.all.cpu.user",
                        "type": "metric",
                        "oneline": "CPU user time",
                        "helptext": "",
                    }  # noqa: E501
                ],
            },
        )
    )

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.discovery import _discover_metrics_impl

        result = await _discover_metrics_impl(
            client, host="", prefix="", search="cpu utilization", limit=50, offset=0
        )
        assert not result.get("isError"), f"Got error: {result}"
        assert search_route.called
        assert "items" in result
        assert result["items"][0]["name"] == "kernel.all.cpu.user"
    finally:
        await client.close()


@respx.mock
async def test_discover_metrics_both_prefix_and_search_raises_error(config):
    """pcp_discover_metrics raises MCP error if both prefix and search are provided."""
    client = PmproxyClient(config)
    try:
        from pmmcp.tools.discovery import _discover_metrics_impl

        result = await _discover_metrics_impl(
            client, host="", prefix="kernel", search="cpu", limit=50, offset=0
        )
        assert result.get("isError") is True
        text = result["content"][0]["text"]
        assert (
            "mutually exclusive" in text.lower()
            or "both" in text.lower()
            or "exclusive" in text.lower()
        )  # noqa: E501
    finally:
        await client.close()


@respx.mock
async def test_get_metric_info_returns_full_metadata(config):
    """pcp_get_metric_info returns Metric[] with full fields."""
    respx.get(f"{PMPROXY_BASE}/pmapi/context").mock(return_value=_mock_context())
    respx.get(f"{PMPROXY_BASE}/pmapi/metric").mock(
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
                        "text-help": "The 1, 5 and 15 minute load averages",
                    }
                ],
            },
        )
    )
    respx.get(f"{PMPROXY_BASE}/pmapi/indom").mock(
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

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.discovery import _get_metric_info_impl

        result = await _get_metric_info_impl(client, names=["kernel.all.load"], host="")
        assert isinstance(result, list), f"Expected list, got: {result}"
        assert len(result) == 1
        metric = result[0]
        assert metric["name"] == "kernel.all.load"
        assert metric["type"] == "float"  # normalised to lowercase
        assert metric["semantics"] == "instant"
        assert metric["oneline"] == "1, 5 and 15 minute load average"
        assert metric["helptext"] == "The 1, 5 and 15 minute load averages"
        assert "indom" in metric
    finally:
        await client.close()


@respx.mock
async def test_get_metric_info_unknown_metric_returns_error(config):
    """pcp_get_metric_info unknown metric -> MCP not-found error."""
    respx.get(f"{PMPROXY_BASE}/pmapi/context").mock(return_value=_mock_context())
    respx.get(f"{PMPROXY_BASE}/pmapi/metric").mock(
        return_value=httpx.Response(
            400,
            json={"message": "Unknown metric name: no.such.metric", "success": False},
        )
    )

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.discovery import _get_metric_info_impl

        result = await _get_metric_info_impl(client, names=["no.such.metric"], host="")
        assert result.get("isError") is True
    finally:
        await client.close()
