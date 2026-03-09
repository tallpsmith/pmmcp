"""Tests for pcp_search tool (T020)."""

from __future__ import annotations

import httpx
import pytest
import respx

from pmmcp.client import PmproxyClient
from pmmcp.config import PmproxyConfig

PMPROXY_BASE = "http://localhost:44322"


@pytest.fixture
def config():
    return PmproxyConfig(url=PMPROXY_BASE, timeout=5.0)


@respx.mock
async def test_search_returns_paginated_search_results(config):
    """pcp_search returns PaginatedResponse[SearchResult] with correct fields."""
    respx.get(f"{PMPROXY_BASE}/search/text").mock(
        return_value=httpx.Response(
            200,
            json={
                "total": 2,
                "elapsed": 0.001,
                "offset": 0,
                "limit": 20,
                "results": [
                    {
                        "name": "kernel.all.load",
                        "type": "metric",
                        "oneline": "1, 5 and 15 minute load average",
                        "helptext": "Extended help text",
                    },
                    {
                        "name": "kernel.all.cpu.user",
                        "type": "metric",
                        "oneline": "CPU user time",
                        "helptext": "",
                    },
                ],
            },
        )
    )

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.search import _search_impl

        result = await _search_impl(client, query="cpu", type="all", limit=20, offset=0)
        assert not result.get("isError"), f"Got error: {result}"
        assert result["total"] == 2
        assert len(result["items"]) == 2
        item = result["items"][0]
        assert item["name"] == "kernel.all.load"
        assert item["type"] == "metric"
        assert "oneline" in item
        assert "helptext" in item
        assert "score" in item
    finally:
        await client.close()


@respx.mock
async def test_search_type_filter_metric(config):
    """pcp_search passes type filter to pmproxy for 'metric' type."""
    route = respx.get(f"{PMPROXY_BASE}/search/text").mock(
        return_value=httpx.Response(
            200, json={"total": 0, "elapsed": 0, "offset": 0, "limit": 20, "results": []}
        )
    )

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.search import _search_impl

        await _search_impl(client, query="cpu", type="metric", limit=20, offset=0)
        url_str = str(route.calls[0].request.url)
        assert "type=metric" in url_str or "type%3Dmetric" in url_str or "metric" in url_str
    finally:
        await client.close()


@respx.mock
async def test_search_type_filter_indom(config):
    """pcp_search handles 'indom' type filter."""
    respx.get(f"{PMPROXY_BASE}/search/text").mock(
        return_value=httpx.Response(
            200, json={"total": 0, "elapsed": 0, "offset": 0, "limit": 20, "results": []}
        )
    )

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.search import _search_impl

        result = await _search_impl(client, query="cpu", type="indom", limit=20, offset=0)
        assert not result.get("isError")
    finally:
        await client.close()


@respx.mock
async def test_search_connection_error_returns_mcp_error(config):
    """pcp_search connection error -> MCP error with suggestion."""
    respx.get(f"{PMPROXY_BASE}/search/text").mock(
        side_effect=httpx.ConnectError("Connection refused")
    )

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.search import _search_impl

        result = await _search_impl(client, query="cpu", type="all", limit=20, offset=0)
        assert result.get("isError") is True
        text = result["content"][0]["text"]
        assert "Connection error" in text
    finally:
        await client.close()


@respx.mock
async def test_search_timeout_returns_mcp_error(config):
    """pcp_search timeout -> MCP timeout error."""
    respx.get(f"{PMPROXY_BASE}/search/text").mock(side_effect=httpx.ReadTimeout("Timeout"))

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.search import _search_impl

        result = await _search_impl(client, query="cpu", type="all", limit=20, offset=0)
        assert result.get("isError") is True
        text = result["content"][0]["text"]
        assert "timeout" in text.lower() or "Timeout" in text
    finally:
        await client.close()


@respx.mock
async def test_search_pmproxy_error_returns_mcp_error(config):
    """pcp_search pmproxy 500 error -> MCP error."""
    respx.get(f"{PMPROXY_BASE}/search/text").mock(
        return_value=httpx.Response(500, json={"message": "RediSearch not configured"})
    )

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.search import _search_impl

        result = await _search_impl(client, query="cpu", type="all", limit=20, offset=0)
        assert result.get("isError") is True
    finally:
        await client.close()


@respx.mock
async def test_search_pagination(config):
    """pcp_search respects limit/offset pagination."""
    respx.get(f"{PMPROXY_BASE}/search/text").mock(
        return_value=httpx.Response(
            200,
            json={
                "total": 100,
                "elapsed": 0.001,
                "offset": 20,
                "limit": 20,
                "results": [
                    {"name": f"metric.{i}", "type": "metric", "oneline": "", "helptext": ""}
                    for i in range(20)
                ],  # noqa: E501
            },
        )
    )

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.search import _search_impl

        result = await _search_impl(client, query="test", type="all", limit=20, offset=20)
        assert result["offset"] == 20
        assert result["limit"] == 20
        assert result["has_more"] is True
        assert result["total"] == 100
    finally:
        await client.close()


# ---------------------------------------------------------------------------
# T022: pcp_search default limit is 50
# ---------------------------------------------------------------------------


def test_search_default_limit_is_50():
    """pcp_search tool default limit is 50 (FR-007)."""
    import inspect

    from pmmcp.tools.search import pcp_search

    sig = inspect.signature(pcp_search)
    assert sig.parameters["limit"].default == 50
