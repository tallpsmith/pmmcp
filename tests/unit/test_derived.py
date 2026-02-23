"""Tests for pcp_derive_metric tool (T021)."""

from __future__ import annotations

import httpx
import pytest
import respx

from pmmcp.client import PmproxyClient
from pmmcp.config import PmproxyConfig

PMPROXY_BASE = "http://localhost:44322"
TEST_CONTEXT = 348734


@pytest.fixture
def config():
    return PmproxyConfig(url=PMPROXY_BASE, timeout=5.0)


@respx.mock
async def test_derive_metric_success(config):
    """pcp_derive_metric returns success=True on successful derivation."""
    respx.get(f"{PMPROXY_BASE}/pmapi/context").mock(
        return_value=httpx.Response(
            200, json={"context": TEST_CONTEXT, "hostspec": "localhost", "labels": {}}
        )
    )
    respx.get(f"{PMPROXY_BASE}/pmapi/derive").mock(
        return_value=httpx.Response(200, json={"context": TEST_CONTEXT, "success": True})
    )

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.derived import _derive_metric_impl

        result = await _derive_metric_impl(
            client,
            name="derived.cpu.total",
            expr="100 * (kernel.all.cpu.user + kernel.all.cpu.sys) / hinv.ncpu",
            host="",
        )
        assert result.get("success") is True
        assert result.get("name") == "derived.cpu.total"
        assert "message" in result
    finally:
        await client.close()


@respx.mock
async def test_derive_metric_failure_returns_mcp_error(config):
    """pcp_derive_metric pmproxy error -> MCP error with pmproxy message."""
    respx.get(f"{PMPROXY_BASE}/pmapi/context").mock(
        return_value=httpx.Response(
            200, json={"context": TEST_CONTEXT, "hostspec": "localhost", "labels": {}}
        )
    )
    respx.get(f"{PMPROXY_BASE}/pmapi/derive").mock(
        return_value=httpx.Response(
            200,
            json={
                "context": TEST_CONTEXT,
                "message": "Semantic error in expression: unknown metric bad.metric.name",
                "success": False,
            },
        )
    )

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.derived import _derive_metric_impl

        result = await _derive_metric_impl(
            client,
            name="derived.bad",
            expr="bad.metric.name + 1",
            host="",
        )
        assert result.get("isError") is True
        text = result["content"][0]["text"]
        assert "semantic" in text.lower() or "error" in text.lower() or "bad.metric" in text.lower()
    finally:
        await client.close()


@respx.mock
async def test_derive_metric_connection_error(config):
    """pcp_derive_metric connection error -> MCP error."""
    respx.get(f"{PMPROXY_BASE}/pmapi/context").mock(
        side_effect=httpx.ConnectError("Connection refused")
    )

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.derived import _derive_metric_impl

        result = await _derive_metric_impl(
            client, name="derived.cpu.total", expr="kernel.all.cpu.user", host=""
        )
        assert result.get("isError") is True
        text = result["content"][0]["text"]
        assert "Connection error" in text
    finally:
        await client.close()


@respx.mock
async def test_derive_metric_pmproxy_api_error(config):
    """pcp_derive_metric 400 error -> MCP error with context."""
    respx.get(f"{PMPROXY_BASE}/pmapi/context").mock(
        return_value=httpx.Response(
            200, json={"context": TEST_CONTEXT, "hostspec": "localhost", "labels": {}}
        )
    )
    respx.get(f"{PMPROXY_BASE}/pmapi/derive").mock(
        return_value=httpx.Response(
            400,
            json={"message": "Invalid expression syntax", "success": False},
        )
    )

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.derived import _derive_metric_impl

        result = await _derive_metric_impl(
            client,
            name="derived.bad",
            expr="!!!invalid!!!",
            host="",
        )
        assert result.get("isError") is True
    finally:
        await client.close()
