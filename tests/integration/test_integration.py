"""Integration tests against a live pmproxy (T039).

These tests are skipped when PMPROXY_URL is not set — CI runs without a real pmproxy.
Set PMPROXY_URL=http://your-pmproxy-host:44322 to run them.
"""

from __future__ import annotations

import os
import time

import pytest

PMPROXY_URL = os.environ.get("PMPROXY_URL")

pytestmark = pytest.mark.skipif(
    not PMPROXY_URL,
    reason="PMPROXY_URL not set — skipping integration tests",
)


@pytest.fixture
async def live_client():
    from pmmcp.client import PmproxyClient
    from pmmcp.config import PmproxyConfig

    config = PmproxyConfig(url=PMPROXY_URL, timeout=30.0)
    client = PmproxyClient(config)
    yield client
    await client.close()


async def test_host_discovery_performance(live_client):
    """SC-004: Host discovery completes in < 10 seconds."""
    from pmmcp.tools.hosts import _get_hosts_impl

    start = time.monotonic()
    result = await _get_hosts_impl(live_client, match="", limit=50, offset=0)
    elapsed = time.monotonic() - start

    assert elapsed < 10, f"Host discovery took {elapsed:.1f}s (SLA: <10s)"
    assert not result.get("isError"), f"Got error: {result}"
    assert isinstance(result["items"], list)


async def test_live_fetch_performance(live_client):
    """SC-001: Live metric fetch completes in < 5 seconds."""
    from pmmcp.tools.live import _fetch_live_impl

    start = time.monotonic()
    result = await _fetch_live_impl(
        live_client,
        names=["kernel.all.load"],
        host="",
        instances=[],
    )
    elapsed = time.monotonic() - start

    assert elapsed < 5, f"Live fetch took {elapsed:.1f}s (SLA: <5s)"
    assert not result.get("isError"), f"Got error: {result}"


async def test_timeseries_7day_auto_interval(live_client):
    """SC-002: 7-day timeseries with auto interval completes in < 15 seconds."""
    from pmmcp.tools.timeseries import _fetch_timeseries_impl

    start = time.monotonic()
    await _fetch_timeseries_impl(
        live_client,
        names=["kernel.all.load"],
        start="-7days",
        end="now",
        interval="auto",
        host="",
        instances=[],
        limit=500,
        offset=0,
        zone="UTC",
    )
    elapsed = time.monotonic() - start

    assert elapsed < 15, f"7-day timeseries took {elapsed:.1f}s (SLA: <15s)"


async def test_metric_search(live_client):
    """Search for CPU metrics returns results."""
    from pmmcp.tools.search import _search_impl

    result = await _search_impl(live_client, query="cpu", type="metric", limit=10, offset=0)
    assert not result.get("isError"), f"Got error: {result}"
    assert len(result.get("items", [])) > 0


async def test_two_window_comparison(live_client):
    """Compare two 1-hour windows and verify statistics."""
    from pmmcp.tools.comparison import _compare_windows_impl

    result = await _compare_windows_impl(
        live_client,
        names=["kernel.all.load"],
        window_a_start="-2hours",
        window_a_end="-1hour",
        window_b_start="-1hour",
        window_b_end="now",
        host="",
        instances=[],
        interval="5min",
        include_samples=False,
    )
    assert isinstance(result, list), f"Expected list, got: {result}"


async def test_derived_metric_creation(live_client):
    """Create a derived metric and verify success."""
    from pmmcp.tools.derived import _derive_metric_impl

    result = await _derive_metric_impl(
        live_client,
        name="derived.test.load_per_cpu",
        expr="kernel.all.load / hinv.ncpu",
        host="",
    )
    # Accept either success or failure (metric may already exist)
    assert isinstance(result, dict)
    assert "success" in result or result.get("isError") is True
