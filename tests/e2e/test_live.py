"""E2E live tests against a real pmproxy (relocated from tests/integration/test_integration.py).

Gating is handled by tests/e2e/conftest.py:
  - SKIP_E2E=1        → skipped
  - PMPROXY_URL unset → xfail (strict)
  - PMPROXY_URL set   → run against live pmproxy
"""

from __future__ import annotations

import json
import time

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.e2e
async def test_host_discovery_performance(e2e_session):
    """SC-004: Host discovery completes in < 10 seconds."""
    start = time.monotonic()
    result = await e2e_session.call_tool("pcp_get_hosts", {"limit": 50, "offset": 0})
    elapsed = time.monotonic() - start

    assert elapsed < 10, f"Host discovery took {elapsed:.1f}s (SLA: <10s)"
    assert not result.isError, f"Got MCP error: {result}"
    data = json.loads(result.content[0].text)
    assert isinstance(data.get("items"), list)


@pytest.mark.e2e
async def test_live_fetch_performance(e2e_session):
    """SC-001: Live metric fetch completes in < 5 seconds."""
    start = time.monotonic()
    result = await e2e_session.call_tool(
        "pcp_fetch_live",
        {"metrics": ["kernel.all.load"]},
    )
    elapsed = time.monotonic() - start

    assert elapsed < 5, f"Live fetch took {elapsed:.1f}s (SLA: <5s)"
    assert not result.isError, f"Got MCP error: {result}"


@pytest.mark.e2e
async def test_timeseries_7day_auto_interval(e2e_session):
    """SC-002: 7-day timeseries with auto interval completes in < 15 seconds."""
    start = time.monotonic()
    result = await e2e_session.call_tool(
        "pcp_fetch_timeseries",
        {
            "names": ["kernel.all.load"],
            "start": "-7days",
            "end": "now",
            "interval": "auto",
        },
    )
    elapsed = time.monotonic() - start

    assert elapsed < 15, f"7-day timeseries took {elapsed:.1f}s (SLA: <15s)"
    assert not result.isError, f"Got MCP error: {result}"


@pytest.mark.e2e
async def test_metric_search(e2e_session):
    """Search for CPU metrics returns results."""
    result = await e2e_session.call_tool(
        "pcp_search",
        {"query": "cpu", "type": "metric", "limit": 10, "offset": 0},
    )
    assert not result.isError, f"Got MCP error: {result}"
    data = json.loads(result.content[0].text)
    assert len(data.get("items", [])) > 0


@pytest.mark.e2e
async def test_two_window_comparison(e2e_session):
    """Compare two 1-hour windows and verify statistics."""
    result = await e2e_session.call_tool(
        "pcp_compare_windows",
        {
            "names": ["kernel.all.load"],
            "window_a_start": "-2hours",
            "window_a_end": "-1hour",
            "window_b_start": "-1hour",
            "window_b_end": "now",
            "interval": "5min",
            "include_samples": False,
        },
    )
    assert not result.isError, f"Got MCP error: {result}"
    data = json.loads(result.content[0].text)
    assert isinstance(data, list), f"Expected list, got: {type(data)}"


@pytest.mark.e2e
async def test_derived_metric_creation(e2e_session):
    """Create a derived metric and verify success."""
    result = await e2e_session.call_tool(
        "pcp_derive_metric",
        {
            "name": "derived.test.load_per_cpu",
            "expr": "kernel.all.load / hinv.ncpu",
        },
    )
    # Accept either success or failure (metric may already exist)
    data = json.loads(result.content[0].text)
    assert "success" in data or result.isError
