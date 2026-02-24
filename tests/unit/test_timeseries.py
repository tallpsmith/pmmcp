"""Tests for pcp_fetch_timeseries and pcp_query_series tools (T019)."""

from __future__ import annotations

import httpx
import pytest
import respx

from pmmcp.client import PmproxyClient
from pmmcp.config import PmproxyConfig

PMPROXY_BASE = "http://localhost:44322"
TEST_SERIES = "605fc77742cd0317597291329561ac4e50c0dd12"


@pytest.fixture
def config():
    return PmproxyConfig(url=PMPROXY_BASE, timeout=5.0)


def _make_values(series_id: str, count: int = 3) -> list[dict]:
    return [
        {"series": series_id, "timestamp": 1547483646.0 + i * 60, "value": str(i * 10)}
        for i in range(count)
    ]


@respx.mock
async def test_fetch_timeseries_auto_interval(config):
    """pcp_fetch_timeseries resolves 'auto' interval before calling pmproxy."""
    respx.get(f"{PMPROXY_BASE}/series/query").mock(
        return_value=httpx.Response(200, json=[TEST_SERIES])
    )
    respx.get(f"{PMPROXY_BASE}/series/values").mock(
        return_value=httpx.Response(200, json=_make_values(TEST_SERIES))
    )
    respx.get(f"{PMPROXY_BASE}/series/descs").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "series": TEST_SERIES,
                    "source": "src",
                    "pmid": "1.0.0",
                    "indom": "none",
                    "semantics": "instant",
                    "type": "u32",
                    "units": "count",
                }
            ],  # noqa: E501
        )
    )
    respx.get(f"{PMPROXY_BASE}/series/instances").mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{PMPROXY_BASE}/series/labels").mock(return_value=httpx.Response(200, json=[]))

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.timeseries import _fetch_timeseries_impl

        result = await _fetch_timeseries_impl(
            client,
            names=["kernel.all.load"],
            start="-1hour",
            end="now",
            interval="auto",
            host="",
            instances=[],
            limit=500,
            offset=0,
            zone="UTC",
        )
        assert not result.get("isError"), f"Got error: {result}"
        # Verify interval was resolved (not 'auto')
        values_call = None
        for call in respx.calls:
            if "/series/values" in str(call.request.url):
                values_call = call
                break
        if values_call:
            url_str = str(values_call.request.url)
            assert "auto" not in url_str, "interval='auto' must be resolved before calling pmproxy"
    finally:
        await client.close()


@respx.mock
async def test_fetch_timeseries_paginated_output(config):
    """pcp_fetch_timeseries returns paginated output grouped by metric/instance."""
    respx.get(f"{PMPROXY_BASE}/series/query").mock(
        return_value=httpx.Response(200, json=[TEST_SERIES])
    )
    respx.get(f"{PMPROXY_BASE}/series/values").mock(
        return_value=httpx.Response(200, json=_make_values(TEST_SERIES, count=3))
    )
    respx.get(f"{PMPROXY_BASE}/series/descs").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "series": TEST_SERIES,
                    "source": "src",
                    "pmid": "1.0.0",
                    "indom": "none",
                    "semantics": "instant",
                    "type": "u32",
                    "units": "count",
                }
            ],  # noqa: E501
        )
    )
    respx.get(f"{PMPROXY_BASE}/series/instances").mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{PMPROXY_BASE}/series/labels").mock(
        return_value=httpx.Response(
            200, json=[{"series": TEST_SERIES, "labels": {"metric.name": "kernel.all.load"}}]
        )  # noqa: E501
    )

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.timeseries import _fetch_timeseries_impl

        result = await _fetch_timeseries_impl(
            client,
            names=["kernel.all.load"],
            start="-1hour",
            end="now",
            interval="15s",
            host="",
            instances=[],
            limit=500,
            offset=0,
            zone="UTC",
        )
        assert not result.get("isError"), f"Got error: {result}"
        assert "items" in result
        assert len(result["items"]) > 0
        item = result["items"][0]
        assert "samples" in item
    finally:
        await client.close()


@respx.mock
async def test_fetch_timeseries_500_point_default_limit(config):
    """pcp_fetch_timeseries enforces 500-point default limit."""
    respx.get(f"{PMPROXY_BASE}/series/query").mock(
        return_value=httpx.Response(200, json=[TEST_SERIES])
    )
    respx.get(f"{PMPROXY_BASE}/series/values").mock(
        return_value=httpx.Response(200, json=_make_values(TEST_SERIES, count=3))
    )
    respx.get(f"{PMPROXY_BASE}/series/descs").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "series": TEST_SERIES,
                    "source": "src",
                    "pmid": "1.0.0",
                    "indom": "none",
                    "semantics": "instant",
                    "type": "u32",
                    "units": "count",
                }
            ],  # noqa: E501
        )
    )
    respx.get(f"{PMPROXY_BASE}/series/instances").mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{PMPROXY_BASE}/series/labels").mock(return_value=httpx.Response(200, json=[]))

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.timeseries import _fetch_timeseries_impl

        await _fetch_timeseries_impl(
            client,
            names=["kernel.all.load"],
            start="-1hour",
            end="now",
            interval="15s",
            host="",
            instances=[],
            limit=500,
            offset=0,
            zone="UTC",
        )
        # The samples parameter passed to pmproxy should be <= 500
        for call in respx.calls:
            if "/series/values" in str(call.request.url):
                url_str = str(call.request.url)
                if "samples=" in url_str:
                    import re

                    m = re.search(r"samples=(\d+)", url_str)
                    if m:
                        assert int(m.group(1)) <= 500
    finally:
        await client.close()


@respx.mock
async def test_query_series_raw_expression(config):
    """pcp_query_series executes raw series expression."""
    respx.get(f"{PMPROXY_BASE}/series/query").mock(
        return_value=httpx.Response(200, json=[TEST_SERIES])
    )
    respx.get(f"{PMPROXY_BASE}/series/values").mock(
        return_value=httpx.Response(200, json=_make_values(TEST_SERIES))
    )
    respx.get(f"{PMPROXY_BASE}/series/descs").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "series": TEST_SERIES,
                    "source": "src",
                    "pmid": "1.0.0",
                    "indom": "none",
                    "semantics": "instant",
                    "type": "u32",
                    "units": "count",
                }
            ],  # noqa: E501
        )
    )
    respx.get(f"{PMPROXY_BASE}/series/instances").mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{PMPROXY_BASE}/series/labels").mock(return_value=httpx.Response(200, json=[]))

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.timeseries import _query_series_impl

        result = await _query_series_impl(
            client,
            expr='kernel.percpu.cpu.user{hostname=="web-01"}',
            start="-1hour",
            end="now",
            interval="15s",
            limit=500,
            offset=0,
        )
        assert not result.get("isError"), f"Got error: {result}"
        assert "items" in result
    finally:
        await client.close()


@respx.mock
async def test_fetch_timeseries_multi_metric_queries_separately(config):
    """pcp_fetch_timeseries queries each metric individually, not with 'or' expression."""
    SERIES_A = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    SERIES_B = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"

    query_route = respx.get(f"{PMPROXY_BASE}/series/query").mock(
        side_effect=[
            httpx.Response(200, json=[SERIES_A]),
            httpx.Response(200, json=[SERIES_B]),
        ]
    )
    respx.get(f"{PMPROXY_BASE}/series/values").mock(
        side_effect=[
            httpx.Response(200, json=_make_values(SERIES_A)),
            httpx.Response(200, json=_make_values(SERIES_B)),
        ]
    )
    respx.get(f"{PMPROXY_BASE}/series/labels").mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{PMPROXY_BASE}/series/instances").mock(return_value=httpx.Response(200, json=[]))

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.timeseries import _fetch_timeseries_impl

        result = await _fetch_timeseries_impl(
            client,
            names=["kernel.all.cpu.user", "kernel.all.cpu.sys"],
            start="-1hour",
            end="now",
            interval="5min",
            host="",
            instances=[],
            limit=500,
            offset=0,
            zone="UTC",
        )
        assert not result.get("isError"), f"Got error: {result}"
        # Two separate /series/query calls, one per metric
        assert query_route.call_count == 2
        exprs = [str(c.request.url) for c in query_route.calls]
        assert all("or" not in e for e in exprs), "Should not use 'or' expression"
        assert result["total"] == 2
    finally:
        await client.close()


@respx.mock
async def test_fetch_timeseries_natural_sample_cap(config):
    """samples sent to pmproxy is capped at natural fit (window/interval), not raw limit."""
    respx.get(f"{PMPROXY_BASE}/series/query").mock(
        return_value=httpx.Response(200, json=[TEST_SERIES])
    )
    values_route = respx.get(f"{PMPROXY_BASE}/series/values").mock(
        return_value=httpx.Response(200, json=_make_values(TEST_SERIES))
    )
    respx.get(f"{PMPROXY_BASE}/series/labels").mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{PMPROXY_BASE}/series/instances").mock(return_value=httpx.Response(200, json=[]))

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.timeseries import _fetch_timeseries_impl

        await _fetch_timeseries_impl(
            client,
            names=["kernel.all.cpu.user"],
            start="-1hour",
            end="now",
            interval="15s",  # 3600/15 = 240 natural samples
            host="",
            instances=[],
            limit=500,  # higher than natural — should be capped at 240
            offset=0,
            zone="UTC",
        )
        assert values_route.called
        import re

        url_str = str(values_route.calls[0].request.url)
        m = re.search(r"samples=(\d+)", url_str)
        assert m is not None, f"samples param missing from URL: {url_str}"
        assert int(m.group(1)) == 240, f"Expected 240 natural samples, got {m.group(1)}"
    finally:
        await client.close()


@respx.mock
async def test_fetch_timeseries_remote_protocol_error_returns_mcp_error(config):
    """httpx.RemoteProtocolError (server disconnect) is surfaced as MCP error, not a crash."""
    respx.get(f"{PMPROXY_BASE}/series/query").mock(
        side_effect=httpx.RemoteProtocolError("Server disconnected without sending a response.")
    )

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.timeseries import _fetch_timeseries_impl

        result = await _fetch_timeseries_impl(
            client,
            names=["kernel.all.cpu.user"],
            start="-24hours",
            end="now",
            interval="5min",
            host="",
            instances=[],
            limit=500,
            offset=0,
            zone="UTC",
        )
        assert result.get("isError") is True
        text = result["content"][0]["text"]
        assert "connection" in text.lower() or "disconnected" in text.lower()
    finally:
        await client.close()


@respx.mock
async def test_fetch_timeseries_timeout_returns_mcp_error(config):
    """pcp_fetch_timeseries timeout -> MCP timeout error with suggestion."""
    respx.get(f"{PMPROXY_BASE}/series/query").mock(side_effect=httpx.ReadTimeout("Timeout"))

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.timeseries import _fetch_timeseries_impl

        result = await _fetch_timeseries_impl(
            client,
            names=["kernel.all.load"],
            start="-1hour",
            end="now",
            interval="15s",
            host="",
            instances=[],
            limit=500,
            offset=0,
            zone="UTC",
        )
        assert result.get("isError") is True
        text = result["content"][0]["text"]
        assert "timeout" in text.lower()
    finally:
        await client.close()
