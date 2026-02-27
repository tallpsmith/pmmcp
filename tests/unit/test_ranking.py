"""Unit tests for pcp_rank_hosts tool."""

from __future__ import annotations

import httpx
import pytest
import respx

from pmmcp.client import PmproxyClient
from pmmcp.config import PmproxyConfig

PMPROXY_BASE = "http://localhost:44322"
SERIES_A = "aaa0000000000000000000000000000000000001"
SERIES_B = "bbb0000000000000000000000000000000000002"
SERIES_C = "ccc0000000000000000000000000000000000003"


@pytest.fixture
def config():
    return PmproxyConfig(url=PMPROXY_BASE, timeout=5.0)


def _make_values(series_id: str, values: list[float], base_ts: float = 1547483646.0) -> list[dict]:
    return [
        {"series": series_id, "timestamp": base_ts + i * 60, "value": str(v)}
        for i, v in enumerate(values)
    ]


@respx.mock
async def test_rank_hosts_basic_ranking(config):
    """pcp_rank_hosts ranks hosts by mean value and identifies outlier."""
    # Three hosts: host-a (high CPU), host-b (medium), host-c (low)
    host_a_values = [90.0, 92.0, 91.0, 93.0, 90.0]  # mean ~91.2
    host_b_values = [50.0, 52.0, 51.0, 50.0, 52.0]  # mean ~51.0
    host_c_values = [10.0, 11.0, 10.0, 12.0, 11.0]  # mean ~10.8

    respx.get(f"{PMPROXY_BASE}/series/query").mock(
        return_value=httpx.Response(200, json=[SERIES_A, SERIES_B, SERIES_C])
    )
    respx.get(f"{PMPROXY_BASE}/series/values").mock(
        return_value=httpx.Response(
            200,
            json=(
                _make_values(SERIES_A, host_a_values)
                + _make_values(SERIES_B, host_b_values)
                + _make_values(SERIES_C, host_c_values)
            ),
        )
    )
    respx.get(f"{PMPROXY_BASE}/series/labels").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "series": SERIES_A,
                    "labels": {
                        "metric.name": "kernel.all.cpu.user",
                        "hostname": "host-a",
                    },
                },
                {
                    "series": SERIES_B,
                    "labels": {
                        "metric.name": "kernel.all.cpu.user",
                        "hostname": "host-b",
                    },
                },
                {
                    "series": SERIES_C,
                    "labels": {
                        "metric.name": "kernel.all.cpu.user",
                        "hostname": "host-c",
                    },
                },
            ],
        )
    )

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.ranking import _rank_hosts_impl

        result = await _rank_hosts_impl(
            client,
            metric="kernel.all.cpu.user",
            start="-1hour",
            end="now",
            criterion="mean",
            outlier_threshold=2.0,
            interval="5min",
        )
        assert isinstance(result, dict), f"Expected dict, got: {result}"
        assert "hosts" in result
        assert "cluster_summary" in result
        hosts = result["hosts"]
        assert len(hosts) == 3
        # Sorted descending by mean — host-a first
        assert hosts[0]["hostname"] == "host-a"
        assert hosts[-1]["hostname"] == "host-c"
        # All fields present
        assert "stats" in hosts[0]
        assert "z_score" in hosts[0]
        assert "is_outlier" in hosts[0]
        # cluster summary populated
        cs = result["cluster_summary"]
        assert cs["host_count"] == 3
        assert cs["cluster_mean"] > 0
    finally:
        await client.close()


@respx.mock
async def test_rank_hosts_invalid_criterion(config):
    """pcp_rank_hosts returns MCP error for invalid criterion."""
    client = PmproxyClient(config)
    try:
        from pmmcp.tools.ranking import _rank_hosts_impl

        result = await _rank_hosts_impl(
            client,
            metric="kernel.all.cpu.user",
            start="-1hour",
            end="now",
            criterion="median",  # invalid
            outlier_threshold=2.0,
            interval="5min",
        )
        assert isinstance(result, dict)
        assert result.get("isError") is True
    finally:
        await client.close()


@respx.mock
async def test_rank_hosts_empty_series(config):
    """pcp_rank_hosts returns empty hosts list when no series found."""
    respx.get(f"{PMPROXY_BASE}/series/query").mock(return_value=httpx.Response(200, json=[]))

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.ranking import _rank_hosts_impl

        result = await _rank_hosts_impl(
            client,
            metric="nonexistent.metric",
            start="-1hour",
            end="now",
            criterion="mean",
            outlier_threshold=2.0,
            interval="5min",
        )
        assert isinstance(result, dict)
        assert result["hosts"] == []
    finally:
        await client.close()


@respx.mock
async def test_rank_hosts_connection_error(config):
    """pcp_rank_hosts returns MCP error on connection failure."""
    respx.get(f"{PMPROXY_BASE}/series/query").mock(
        side_effect=httpx.ConnectError("Connection refused")
    )

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.ranking import _rank_hosts_impl

        result = await _rank_hosts_impl(
            client,
            metric="kernel.all.cpu.user",
            start="-1hour",
            end="now",
            criterion="mean",
            outlier_threshold=2.0,
            interval="5min",
        )
        assert result.get("isError") is True
    finally:
        await client.close()


@respx.mock
async def test_rank_hosts_p95_criterion(config):
    """pcp_rank_hosts uses p95 criterion when specified."""
    respx.get(f"{PMPROXY_BASE}/series/query").mock(
        return_value=httpx.Response(200, json=[SERIES_A])
    )
    respx.get(f"{PMPROXY_BASE}/series/values").mock(
        return_value=httpx.Response(200, json=_make_values(SERIES_A, [10.0, 20.0, 30.0]))
    )
    respx.get(f"{PMPROXY_BASE}/series/labels").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "series": SERIES_A,
                    "labels": {"metric.name": "kernel.all.cpu.user", "hostname": "host-a"},
                }
            ],
        )
    )

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.ranking import _rank_hosts_impl

        result = await _rank_hosts_impl(
            client,
            metric="kernel.all.cpu.user",
            start="-1hour",
            end="now",
            criterion="p95",
            outlier_threshold=2.0,
            interval="5min",
        )
        assert isinstance(result, dict)
        assert result["criterion"] == "p95"
        assert result["hosts"][0]["criterion_value"] == result["hosts"][0]["stats"]["p95"]
    finally:
        await client.close()
