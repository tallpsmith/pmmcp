"""Unit tests for pcp_correlate_metrics tool."""

from __future__ import annotations

import httpx
import pytest
import respx

from pmmcp.client import PmproxyClient
from pmmcp.config import PmproxyConfig

PMPROXY_BASE = "http://localhost:44322"
SERIES_CPU = "aaa0000000000000000000000000000000000001"
SERIES_DISK = "bbb0000000000000000000000000000000000002"
SERIES_MEM = "ccc0000000000000000000000000000000000003"


@pytest.fixture
def config():
    return PmproxyConfig(url=PMPROXY_BASE, timeout=5.0)


def _make_values(series_id: str, values: list[float], base_ts: float = 1547483646.0) -> list[dict]:
    return [
        {"series": series_id, "timestamp": base_ts + i * 60, "value": str(v)}
        for i, v in enumerate(values)
    ]


def _setup_two_metric_mock(
    base_url: str,
    cpu_vals: list[float],
    disk_vals: list[float],
):
    """Set up respx mocks for a two-metric correlation test."""
    respx.get(f"{base_url}/series/query").mock(
        return_value=httpx.Response(200, json=[SERIES_CPU, SERIES_DISK])
    )
    respx.get(f"{base_url}/series/values").mock(
        return_value=httpx.Response(
            200,
            json=_make_values(SERIES_CPU, cpu_vals) + _make_values(SERIES_DISK, disk_vals),
        )
    )
    respx.get(f"{base_url}/series/labels").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "series": SERIES_CPU,
                    "labels": {"metric.name": "kernel.all.cpu.user"},
                },
                {
                    "series": SERIES_DISK,
                    "labels": {"metric.name": "disk.all.read"},
                },
            ],
        )
    )
    respx.get(f"{base_url}/series/instances").mock(return_value=httpx.Response(200, json=[]))


@respx.mock
async def test_correlate_metrics_high_positive_correlation(config):
    """pcp_correlate_metrics returns strong positive r for perfectly correlated metrics."""
    # Perfectly correlated: cpu = disk * 2
    vals = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    cpu_vals = [v * 2 for v in vals]
    disk_vals = vals

    _setup_two_metric_mock(PMPROXY_BASE, cpu_vals, disk_vals)

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.correlation import _correlate_metrics_impl

        result = await _correlate_metrics_impl(
            client,
            metrics=["kernel.all.cpu.user", "disk.all.read"],
            start="-1hour",
            end="now",
            host="",
            interval="5min",
        )
        assert isinstance(result, dict), f"Expected dict, got: {result}"
        assert "correlations" in result
        corrs = result["correlations"]
        assert len(corrs) == 1
        pair = corrs[0]
        assert abs(pair["r"] - 1.0) < 0.001, f"Expected r~1.0, got {pair['r']}"
        assert pair["strength"] in ("very strong", "strong")
        assert pair["direction"] == "positive"
        assert "interpretation" in pair
    finally:
        await client.close()


@respx.mock
async def test_correlate_metrics_negative_correlation(config):
    """pcp_correlate_metrics detects negative correlation."""
    # Anti-correlated
    cpu_vals = [10.0, 9.0, 8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0]
    disk_vals = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]

    _setup_two_metric_mock(PMPROXY_BASE, cpu_vals, disk_vals)

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.correlation import _correlate_metrics_impl

        result = await _correlate_metrics_impl(
            client,
            metrics=["kernel.all.cpu.user", "disk.all.read"],
            start="-1hour",
            end="now",
            host="",
            interval="5min",
        )
        assert isinstance(result, dict)
        corrs = result["correlations"]
        assert len(corrs) == 1
        assert corrs[0]["r"] < -0.9
        assert corrs[0]["direction"] == "negative"
    finally:
        await client.close()


@respx.mock
async def test_correlate_metrics_too_few_metrics(config):
    """pcp_correlate_metrics returns MCP error when fewer than 2 metrics given."""
    client = PmproxyClient(config)
    try:
        from pmmcp.tools.correlation import _correlate_metrics_impl

        result = await _correlate_metrics_impl(
            client,
            metrics=["kernel.all.cpu.user"],  # only 1
            start="-1hour",
            end="now",
            host="",
            interval="5min",
        )
        assert result.get("isError") is True
    finally:
        await client.close()


@respx.mock
async def test_correlate_metrics_connection_error(config):
    """pcp_correlate_metrics returns MCP error on connection failure."""
    respx.get(f"{PMPROXY_BASE}/series/query").mock(
        side_effect=httpx.ConnectError("Connection refused")
    )

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.correlation import _correlate_metrics_impl

        result = await _correlate_metrics_impl(
            client,
            metrics=["kernel.all.cpu.user", "disk.all.read"],
            start="-1hour",
            end="now",
            host="",
            interval="5min",
        )
        assert result.get("isError") is True
    finally:
        await client.close()


@respx.mock
async def test_correlate_metrics_three_metrics(config):
    """pcp_correlate_metrics computes 3 pairs for 3 metrics."""
    respx.get(f"{PMPROXY_BASE}/series/query").mock(
        return_value=httpx.Response(200, json=[SERIES_CPU, SERIES_DISK, SERIES_MEM])
    )
    respx.get(f"{PMPROXY_BASE}/series/values").mock(
        return_value=httpx.Response(
            200,
            json=(
                _make_values(SERIES_CPU, [1.0, 2.0, 3.0, 4.0, 5.0])
                + _make_values(SERIES_DISK, [2.0, 4.0, 6.0, 8.0, 10.0])
                + _make_values(SERIES_MEM, [5.0, 4.0, 3.0, 2.0, 1.0])
            ),
        )
    )
    respx.get(f"{PMPROXY_BASE}/series/labels").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"series": SERIES_CPU, "labels": {"metric.name": "cpu"}},
                {"series": SERIES_DISK, "labels": {"metric.name": "disk"}},
                {"series": SERIES_MEM, "labels": {"metric.name": "mem"}},
            ],
        )
    )
    respx.get(f"{PMPROXY_BASE}/series/instances").mock(return_value=httpx.Response(200, json=[]))

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.correlation import _correlate_metrics_impl

        result = await _correlate_metrics_impl(
            client,
            metrics=["cpu", "disk", "mem"],
            start="-1hour",
            end="now",
            host="",
            interval="5min",
        )
        assert isinstance(result, dict)
        # C(3,2) = 3 pairs
        assert len(result["correlations"]) == 3
        # Sorted by |r| descending
        abs_rs = [abs(p["r"]) for p in result["correlations"]]
        assert abs_rs == sorted(abs_rs, reverse=True)
    finally:
        await client.close()
