"""Tests for pcp_get_hosts tool (T017)."""

from __future__ import annotations

import httpx
import pytest
import respx

from pmmcp.client import PmproxyClient
from pmmcp.config import PmproxyConfig

PMPROXY_BASE = "http://localhost:44322"
TEST_SOURCE = "2cd6a38f9339f2dd1f0b4775bda89a9e7244def6"


@pytest.fixture
def config():
    return PmproxyConfig(url=PMPROXY_BASE, timeout=5.0)


@respx.mock
async def test_get_hosts_returns_paginated_response(config):
    """pcp_get_hosts returns PaginatedResponse[Host] with correct fields."""
    respx.get(f"{PMPROXY_BASE}/series/sources").mock(
        return_value=httpx.Response(
            200,
            json=[{"source": TEST_SOURCE, "context": ["www.acme.com", "acme.internal"]}],
        )
    )
    respx.get(f"{PMPROXY_BASE}/series/labels").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"series": TEST_SOURCE, "labels": {"hostname": "www.acme.com", "agent": "linux"}}
            ],  # noqa: E501
        )
    )

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.hosts import _get_hosts_impl

        result = await _get_hosts_impl(client, match="", limit=50, offset=0)
        assert result["has_more"] is False
        assert len(result["items"]) == 1
        host = result["items"][0]
        assert host["source"] == TEST_SOURCE
        assert "www.acme.com" in host["hostnames"]
        assert result["limit"] == 50
        assert result["offset"] == 0
    finally:
        await client.close()


@respx.mock
async def test_get_hosts_glob_match_filter(config):
    """pcp_get_hosts passes match glob to pmproxy."""
    route = respx.get(f"{PMPROXY_BASE}/series/sources").mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get(f"{PMPROXY_BASE}/series/labels").mock(return_value=httpx.Response(200, json=[]))

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.hosts import _get_hosts_impl

        await _get_hosts_impl(client, match="web-*", limit=50, offset=0)
        assert "match" in str(route.calls[0].request.url)
    finally:
        await client.close()


@respx.mock
async def test_get_hosts_pagination(config):
    """pcp_get_hosts respects limit/offset pagination."""
    sources = [{"source": f"source{i:040d}", "context": [f"host{i}.example.com"]} for i in range(3)]
    respx.get(f"{PMPROXY_BASE}/series/sources").mock(return_value=httpx.Response(200, json=sources))
    respx.get(f"{PMPROXY_BASE}/series/labels").mock(return_value=httpx.Response(200, json=[]))

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.hosts import _get_hosts_impl

        result = await _get_hosts_impl(client, match="", limit=2, offset=0)
        assert result["limit"] == 2
        assert len(result["items"]) == 2
        assert result["has_more"] is True

        result2 = await _get_hosts_impl(client, match="", limit=2, offset=2)
        assert len(result2["items"]) == 1
        assert result2["has_more"] is False
    finally:
        await client.close()


@respx.mock
async def test_get_hosts_connection_error_returns_mcp_error(config):
    """pcp_get_hosts connection refused -> MCP error with isError=True."""
    respx.get(f"{PMPROXY_BASE}/series/sources").mock(
        side_effect=httpx.ConnectError("Connection refused")
    )

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.hosts import _get_hosts_impl

        result = await _get_hosts_impl(client, match="", limit=50, offset=0)
        assert result.get("isError") is True
        text = result["content"][0]["text"]
        assert "connection" in text.lower() or "unreachable" in text.lower()
    finally:
        await client.close()
