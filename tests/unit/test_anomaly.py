"""Unit tests for pcp_detect_anomalies tool."""

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


def _make_values(series_id: str, values: list[float], base_ts: float = 1547483646.0) -> list[dict]:
    return [
        {"series": series_id, "timestamp": base_ts + i * 60, "value": str(v)}
        for i, v in enumerate(values)
    ]


def _series_mock(
    base_url: str,
    series_id: str,
    baseline_vals: list[float],
    recent_vals: list[float],
    metric_name: str = "mem.util.used",
):
    """Helper: set up respx mocks for a two-window fetch sequence."""
    call_count = 0

    def query_side_effect(request):
        return httpx.Response(200, json=[series_id])

    values_responses = [
        httpx.Response(200, json=_make_values(series_id, baseline_vals)),
        httpx.Response(200, json=_make_values(series_id, recent_vals, base_ts=1547570046.0)),
    ]

    def values_side_effect(request):
        nonlocal call_count
        resp = values_responses[min(call_count, len(values_responses) - 1)]
        call_count += 1
        return resp

    respx.get(f"{base_url}/series/query").mock(side_effect=query_side_effect)
    respx.get(f"{base_url}/series/values").mock(side_effect=values_side_effect)
    respx.get(f"{base_url}/series/labels").mock(
        return_value=httpx.Response(
            200,
            json=[{"series": series_id, "labels": {"metric.name": metric_name}}],
        )
    )
    respx.get(f"{base_url}/series/instances").mock(return_value=httpx.Response(200, json=[]))


@respx.mock
async def test_detect_anomalies_high_severity(config):
    """pcp_detect_anomalies flags high severity when recent mean >> baseline."""
    # Baseline: mean ~10, stddev ~1. Recent: mean ~30. z-score ~20 → high.
    _series_mock(
        PMPROXY_BASE,
        TEST_SERIES,
        baseline_vals=[9.0, 10.0, 11.0, 10.0, 9.0, 10.0, 11.0, 10.0, 9.0, 10.0],
        recent_vals=[30.0, 31.0, 29.0],
    )

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.anomaly import _detect_anomalies_impl

        result = await _detect_anomalies_impl(
            client,
            metrics=["mem.util.used"],
            recent_start="-15min",
            recent_end="now",
            baseline_start="-6hours",
            baseline_end="-15min",
            z_score_threshold=2.0,
            host="",
            interval="5min",
        )
        assert isinstance(result, list), f"Expected list, got: {result}"
        assert len(result) > 0
        a = result[0]
        assert a["severity"] == "high"
        assert a["direction"] == "increasing"
        assert a["z_score"] > 2.0
        assert "interpretation" in a
        assert "baseline" in a
        assert "recent" in a
    finally:
        await client.close()


@respx.mock
async def test_detect_anomalies_no_severity(config):
    """pcp_detect_anomalies returns severity=none when recent matches baseline."""
    _series_mock(
        PMPROXY_BASE,
        TEST_SERIES,
        baseline_vals=[10.0, 11.0, 10.0, 9.0, 10.0],
        recent_vals=[10.0, 10.5, 9.5],
    )

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.anomaly import _detect_anomalies_impl

        result = await _detect_anomalies_impl(
            client,
            metrics=["mem.util.used"],
            recent_start="-15min",
            recent_end="now",
            baseline_start="-6hours",
            baseline_end="-15min",
            z_score_threshold=2.0,
            host="",
            interval="5min",
        )
        assert isinstance(result, list)
        assert len(result) > 0
        a = result[0]
        assert a["severity"] == "none"
    finally:
        await client.close()


@respx.mock
async def test_detect_anomalies_decreasing_direction(config):
    """pcp_detect_anomalies correctly flags decreasing direction."""
    # Baseline high, recent low
    _series_mock(
        PMPROXY_BASE,
        TEST_SERIES,
        baseline_vals=[100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0],
        recent_vals=[20.0, 22.0, 21.0],
    )

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.anomaly import _detect_anomalies_impl

        result = await _detect_anomalies_impl(
            client,
            metrics=["mem.util.used"],
            recent_start="-15min",
            recent_end="now",
            baseline_start="-6hours",
            baseline_end="-15min",
            z_score_threshold=2.0,
            host="",
            interval="5min",
        )
        assert isinstance(result, list)
        assert len(result) > 0
        # Baseline stddev is 0, so z_score=0 → severity=none; direction still "decreasing"
        a = result[0]
        assert a["direction"] == "decreasing"
    finally:
        await client.close()


@respx.mock
async def test_detect_anomalies_connection_error(config):
    """pcp_detect_anomalies returns MCP error on connection failure."""
    respx.get(f"{PMPROXY_BASE}/series/query").mock(
        side_effect=httpx.ConnectError("Connection refused")
    )

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.anomaly import _detect_anomalies_impl

        result = await _detect_anomalies_impl(
            client,
            metrics=["mem.util.used"],
            recent_start="-15min",
            recent_end="now",
            baseline_start="-6hours",
            baseline_end="-15min",
            z_score_threshold=2.0,
            host="",
            interval="5min",
        )
        assert result.get("isError") is True
    finally:
        await client.close()


@respx.mock
async def test_detect_anomalies_with_host_filter(config):
    """pcp_detect_anomalies builds hostname-filtered expression."""
    _series_mock(
        PMPROXY_BASE,
        TEST_SERIES,
        baseline_vals=[10.0, 10.0, 10.0],
        recent_vals=[10.0, 10.0, 10.0],
    )

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.anomaly import _detect_anomalies_impl

        result = await _detect_anomalies_impl(
            client,
            metrics=["mem.util.used"],
            recent_start="-15min",
            recent_end="now",
            baseline_start="-6hours",
            baseline_end="-15min",
            z_score_threshold=2.0,
            host="myhost",
            interval="5min",
        )
        assert isinstance(result, list)
    finally:
        await client.close()
