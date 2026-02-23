"""Tests for pcp_fetch_live tool (T018)."""

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
async def test_fetch_live_returns_timestamped_values(config):
    """pcp_fetch_live returns timestamped values with instance data."""
    respx.get(f"{PMPROXY_BASE}/pmapi/context").mock(
        return_value=httpx.Response(
            200,
            json={"context": TEST_CONTEXT, "hostspec": "localhost", "labels": {}},
        )
    )
    respx.get(f"{PMPROXY_BASE}/pmapi/fetch").mock(
        return_value=httpx.Response(
            200,
            json={
                "context": TEST_CONTEXT,
                "timestamp": 1547483646.2147431,
                "values": [
                    {
                        "pmid": "60.0.4",
                        "name": "kernel.all.load",
                        "instances": [
                            {"instance": 1, "value": 0.1},
                            {"instance": 5, "value": 0.25},
                        ],
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
                ],
            },
        )
    )

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.live import _fetch_live_impl

        result = await _fetch_live_impl(client, names=["kernel.all.load"], host="", instances=[])
        assert "timestamp" in result
        assert "values" in result
        values = result["values"]
        assert len(values) == 1
        assert values[0]["name"] == "kernel.all.load"
        assert len(values[0]["instances"]) == 2
    finally:
        await client.close()


@respx.mock
async def test_fetch_live_instance_filter(config):
    """pcp_fetch_live filters results to requested instances."""
    respx.get(f"{PMPROXY_BASE}/pmapi/context").mock(
        return_value=httpx.Response(
            200, json={"context": TEST_CONTEXT, "hostspec": "localhost", "labels": {}}
        )
    )
    respx.get(f"{PMPROXY_BASE}/pmapi/fetch").mock(
        return_value=httpx.Response(
            200,
            json={
                "context": TEST_CONTEXT,
                "timestamp": 1547483646.0,
                "values": [
                    {
                        "pmid": "60.0.4",
                        "name": "disk.dev.read",
                        "instances": [
                            {"instance": 0, "value": 100},
                            {"instance": 1, "value": 200},
                        ],
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
                "indom": "60.1",
                "labels": {},
                "instances": [
                    {"instance": 0, "name": "sda", "labels": {}},
                    {"instance": 1, "name": "sdb", "labels": {}},
                ],
            },
        )
    )

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.live import _fetch_live_impl

        result = await _fetch_live_impl(client, names=["disk.dev.read"], host="", instances=["sda"])
        assert not result.get("isError")
        assert len(result["values"][0]["instances"]) == 1
        assert result["values"][0]["instances"][0]["instance"] == "sda"
    finally:
        await client.close()


@respx.mock
async def test_fetch_live_expired_context_retry(config):
    """pcp_fetch_live retries on expired context (403)."""
    context_calls = 0

    def context_side_effect(request):
        nonlocal context_calls
        context_calls += 1
        return httpx.Response(
            200,
            json={"context": TEST_CONTEXT + context_calls, "hostspec": "localhost", "labels": {}},  # noqa: E501
        )

    fetch_calls = 0

    def fetch_side_effect(request):
        nonlocal fetch_calls
        fetch_calls += 1
        if fetch_calls == 1:
            return httpx.Response(403, json={"message": "expired context", "success": False})
        return httpx.Response(
            200,
            json={
                "context": TEST_CONTEXT,
                "timestamp": 1547483646.0,
                "values": [
                    {
                        "pmid": "1.0.0",
                        "name": "mem.util.free",
                        "instances": [{"instance": None, "value": 1024}],
                    }
                ],  # noqa: E501
            },
        )

    respx.get(f"{PMPROXY_BASE}/pmapi/context").mock(side_effect=context_side_effect)
    respx.get(f"{PMPROXY_BASE}/pmapi/fetch").mock(side_effect=fetch_side_effect)
    respx.get(f"{PMPROXY_BASE}/pmapi/indom").mock(
        return_value=httpx.Response(
            200, json={"context": TEST_CONTEXT, "indom": "none", "labels": {}, "instances": []}
        )  # noqa: E501
    )

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.live import _fetch_live_impl

        result = await _fetch_live_impl(client, names=["mem.util.free"], host="", instances=[])
        # Should succeed after retry
        assert not result.get("isError"), f"Expected success after retry but got error: {result}"
    finally:
        await client.close()


@respx.mock
async def test_fetch_live_unknown_metric_returns_mcp_error(config):
    """pcp_fetch_live unknown metric -> MCP not-found error."""
    respx.get(f"{PMPROXY_BASE}/pmapi/context").mock(
        return_value=httpx.Response(
            200, json={"context": TEST_CONTEXT, "hostspec": "localhost", "labels": {}}
        )
    )
    respx.get(f"{PMPROXY_BASE}/pmapi/fetch").mock(
        return_value=httpx.Response(
            400,
            json={"message": "Unknown metric name: no.such.metric", "success": False},
        )
    )

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.live import _fetch_live_impl

        result = await _fetch_live_impl(client, names=["no.such.metric"], host="", instances=[])
        assert result.get("isError") is True
        text = result["content"][0]["text"]
        assert "not found" in text.lower() or "unknown" in text.lower() or "metric" in text.lower()
    finally:
        await client.close()
