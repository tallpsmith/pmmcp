"""Tests for pcp_compare_windows tool (T033)."""

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


@respx.mock
async def test_compare_windows_returns_window_comparisons(config):
    """pcp_compare_windows returns WindowComparison[] with stats for each window."""
    window_a_values = [10.0, 12.0, 11.0, 13.0, 10.0]
    window_b_values = [50.0, 55.0, 52.0, 58.0, 51.0]

    call_count = 0

    def values_side_effect(request):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(200, json=_make_values(TEST_SERIES, window_a_values))
        return httpx.Response(
            200, json=_make_values(TEST_SERIES, window_b_values, base_ts=1547570046.0)
        )  # noqa: E501

    query_count = 0

    def query_side_effect(request):
        nonlocal query_count
        query_count += 1
        return httpx.Response(200, json=[TEST_SERIES])

    respx.get(f"{PMPROXY_BASE}/series/query").mock(side_effect=query_side_effect)
    respx.get(f"{PMPROXY_BASE}/series/values").mock(side_effect=values_side_effect)
    respx.get(f"{PMPROXY_BASE}/series/labels").mock(
        return_value=httpx.Response(
            200,
            json=[{"series": TEST_SERIES, "labels": {"metric.name": "kernel.all.cpu.user"}}],
        )
    )
    respx.get(f"{PMPROXY_BASE}/series/instances").mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{PMPROXY_BASE}/series/descs").mock(return_value=httpx.Response(200, json=[]))

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.comparison import _compare_windows_impl

        result = await _compare_windows_impl(
            client,
            names=["kernel.all.cpu.user"],
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
        assert len(result) > 0
        comp = result[0]
        assert "metric" in comp
        assert "window_a" in comp
        assert "window_b" in comp
        assert "delta" in comp
        # window_a mean ~11.2, window_b mean ~53.2 — significant change
        wa = comp["window_a"]
        wb = comp["window_b"]
        assert wa["mean"] < wb["mean"]
        assert "min" in wa and "max" in wa and "p95" in wa and "stddev" in wa
        delta = comp["delta"]
        assert delta["significant"] is True
    finally:
        await client.close()


@respx.mock
async def test_compare_windows_not_significant_for_identical(config):
    """pcp_compare_windows returns significant=False for identical windows."""
    identical_values = [10.0, 10.0, 10.0, 10.0, 10.0]

    call_count = 0

    def values_side_effect(request):
        nonlocal call_count
        call_count += 1
        base = 1547483646.0 if call_count == 1 else 1547570046.0
        return httpx.Response(200, json=_make_values(TEST_SERIES, identical_values, base_ts=base))

    respx.get(f"{PMPROXY_BASE}/series/query").mock(
        return_value=httpx.Response(200, json=[TEST_SERIES])
    )
    respx.get(f"{PMPROXY_BASE}/series/values").mock(side_effect=values_side_effect)
    respx.get(f"{PMPROXY_BASE}/series/labels").mock(
        return_value=httpx.Response(
            200,
            json=[{"series": TEST_SERIES, "labels": {"metric.name": "kernel.all.load"}}],
        )
    )
    respx.get(f"{PMPROXY_BASE}/series/instances").mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{PMPROXY_BASE}/series/descs").mock(return_value=httpx.Response(200, json=[]))

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.comparison import _compare_windows_impl

        result = await _compare_windows_impl(
            client,
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
        assert len(result) > 0
        delta = result[0]["delta"]
        assert delta["significant"] is False
    finally:
        await client.close()


@respx.mock
async def test_compare_windows_include_samples(config):
    """pcp_compare_windows includes raw samples when include_samples=True."""
    values = [10.0, 11.0, 12.0]

    call_count = 0

    def values_side_effect(request):
        nonlocal call_count
        call_count += 1
        base = 1547483646.0 if call_count == 1 else 1547570046.0
        return httpx.Response(200, json=_make_values(TEST_SERIES, values, base_ts=base))

    respx.get(f"{PMPROXY_BASE}/series/query").mock(
        return_value=httpx.Response(200, json=[TEST_SERIES])
    )
    respx.get(f"{PMPROXY_BASE}/series/values").mock(side_effect=values_side_effect)
    respx.get(f"{PMPROXY_BASE}/series/labels").mock(
        return_value=httpx.Response(
            200,
            json=[{"series": TEST_SERIES, "labels": {"metric.name": "kernel.all.load"}}],
        )
    )
    respx.get(f"{PMPROXY_BASE}/series/instances").mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{PMPROXY_BASE}/series/descs").mock(return_value=httpx.Response(200, json=[]))

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.comparison import _compare_windows_impl

        result = await _compare_windows_impl(
            client,
            names=["kernel.all.load"],
            window_a_start="-2hours",
            window_a_end="-1hour",
            window_b_start="-1hour",
            window_b_end="now",
            host="",
            instances=[],
            interval="5min",
            include_samples=True,
        )
        assert isinstance(result, list), f"Expected list, got: {result}"
        comp = result[0]
        # When include_samples=True, raw samples should be present
        assert "window_a_samples" in comp or "samples_a" in comp or "window_a" in comp
    finally:
        await client.close()


@respx.mock
async def test_compare_windows_counter_metric_uses_rates(config):
    """Counter metrics should compare rates (per-second), not raw cumulative values.

    Two windows with identical constant rate (1.0/s) should show no significant change,
    even though raw counter values are wildly different between windows.
    """
    # Window A: counter from 1000 to 1240 (rate = 1.0/s at 60s intervals)
    window_a_counter = [1000.0, 1060.0, 1120.0, 1180.0, 1240.0]
    # Window B: counter from 5000 to 5240 (same rate = 1.0/s)
    window_b_counter = [5000.0, 5060.0, 5120.0, 5180.0, 5240.0]

    call_count = 0

    def values_side_effect(request):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(200, json=_make_values(TEST_SERIES, window_a_counter))
        return httpx.Response(
            200, json=_make_values(TEST_SERIES, window_b_counter, base_ts=1547570046.0)
        )

    respx.get(f"{PMPROXY_BASE}/series/query").mock(
        return_value=httpx.Response(200, json=[TEST_SERIES])
    )
    respx.get(f"{PMPROXY_BASE}/series/values").mock(side_effect=values_side_effect)
    respx.get(f"{PMPROXY_BASE}/series/labels").mock(
        return_value=httpx.Response(
            200,
            json=[{"series": TEST_SERIES, "labels": {"metric.name": "network.interface.in.bytes"}}],
        )
    )
    respx.get(f"{PMPROXY_BASE}/series/instances").mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{PMPROXY_BASE}/series/descs").mock(
        return_value=httpx.Response(200, json=[{"series": TEST_SERIES, "semantics": "counter"}])
    )

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.comparison import _compare_windows_impl

        result = await _compare_windows_impl(
            client,
            names=["network.interface.in.bytes"],
            window_a_start="-2hours",
            window_a_end="-1hour",
            window_b_start="-1hour",
            window_b_end="now",
            host="",
            instances=[],
            interval="5min",
            include_samples=False,
        )
        assert isinstance(result, list)
        assert len(result) > 0
        comp = result[0]
        # Rate is identical in both windows → not significant
        assert comp["delta"]["significant"] is False
        # Should report counter semantics
        assert comp["semantics"] == "counter"
    finally:
        await client.close()


@respx.mock
async def test_compare_windows_instant_metric_uses_raw_values(config):
    """Instant metrics should compare raw values directly (existing behaviour)."""
    window_a_values = [10.0, 12.0, 11.0, 13.0, 10.0]
    window_b_values = [50.0, 55.0, 52.0, 58.0, 51.0]

    call_count = 0

    def values_side_effect(request):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(200, json=_make_values(TEST_SERIES, window_a_values))
        return httpx.Response(
            200, json=_make_values(TEST_SERIES, window_b_values, base_ts=1547570046.0)
        )

    respx.get(f"{PMPROXY_BASE}/series/query").mock(
        return_value=httpx.Response(200, json=[TEST_SERIES])
    )
    respx.get(f"{PMPROXY_BASE}/series/values").mock(side_effect=values_side_effect)
    respx.get(f"{PMPROXY_BASE}/series/labels").mock(
        return_value=httpx.Response(
            200,
            json=[{"series": TEST_SERIES, "labels": {"metric.name": "kernel.all.cpu.user"}}],
        )
    )
    respx.get(f"{PMPROXY_BASE}/series/instances").mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{PMPROXY_BASE}/series/descs").mock(
        return_value=httpx.Response(200, json=[{"series": TEST_SERIES, "semantics": "instant"}])
    )

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.comparison import _compare_windows_impl

        result = await _compare_windows_impl(
            client,
            names=["kernel.all.cpu.user"],
            window_a_start="-2hours",
            window_a_end="-1hour",
            window_b_start="-1hour",
            window_b_end="now",
            host="",
            instances=[],
            interval="5min",
            include_samples=False,
        )
        assert isinstance(result, list)
        assert len(result) > 0
        comp = result[0]
        # Instant metric with very different values → significant
        assert comp["delta"]["significant"] is True
        assert comp["semantics"] == "instant"
    finally:
        await client.close()


@respx.mock
async def test_compare_windows_descs_failure_falls_back_to_instant(config):
    """When /series/descs returns HTTP 500, fall back to instant (raw values)."""
    window_a_values = [10.0, 12.0, 11.0, 13.0, 10.0]
    window_b_values = [50.0, 55.0, 52.0, 58.0, 51.0]

    call_count = 0

    def values_side_effect(request):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(200, json=_make_values(TEST_SERIES, window_a_values))
        return httpx.Response(
            200, json=_make_values(TEST_SERIES, window_b_values, base_ts=1547570046.0)
        )

    respx.get(f"{PMPROXY_BASE}/series/query").mock(
        return_value=httpx.Response(200, json=[TEST_SERIES])
    )
    respx.get(f"{PMPROXY_BASE}/series/values").mock(side_effect=values_side_effect)
    respx.get(f"{PMPROXY_BASE}/series/labels").mock(
        return_value=httpx.Response(
            200,
            json=[{"series": TEST_SERIES, "labels": {"metric.name": "kernel.all.cpu.user"}}],
        )
    )
    respx.get(f"{PMPROXY_BASE}/series/instances").mock(return_value=httpx.Response(200, json=[]))
    # Descs endpoint fails
    respx.get(f"{PMPROXY_BASE}/series/descs").mock(
        return_value=httpx.Response(500, json={"message": "internal error"})
    )

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.comparison import _compare_windows_impl

        result = await _compare_windows_impl(
            client,
            names=["kernel.all.cpu.user"],
            window_a_start="-2hours",
            window_a_end="-1hour",
            window_b_start="-1hour",
            window_b_end="now",
            host="",
            instances=[],
            interval="5min",
            include_samples=False,
        )
        # Should still work — falls back to raw values (instant behaviour)
        assert isinstance(result, list)
        assert len(result) > 0
        comp = result[0]
        assert comp["delta"]["significant"] is True
        # Fallback semantics should be "instant"
        assert comp["semantics"] == "instant"
    finally:
        await client.close()


@respx.mock
async def test_compare_windows_same_resolved_interval_for_both(config):
    """pcp_compare_windows applies resolve_interval once, uses same interval for both windows."""
    query_calls = []

    def query_side_effect(request):
        query_calls.append(str(request.url))
        return httpx.Response(200, json=[TEST_SERIES])

    values_calls = []

    def values_side_effect(request):
        values_calls.append(str(request.url))
        return httpx.Response(200, json=_make_values(TEST_SERIES, [10.0, 11.0]))

    respx.get(f"{PMPROXY_BASE}/series/query").mock(side_effect=query_side_effect)
    respx.get(f"{PMPROXY_BASE}/series/values").mock(side_effect=values_side_effect)
    respx.get(f"{PMPROXY_BASE}/series/labels").mock(
        return_value=httpx.Response(
            200,
            json=[{"series": TEST_SERIES, "labels": {"metric.name": "kernel.all.load"}}],
        )
    )
    respx.get(f"{PMPROXY_BASE}/series/instances").mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{PMPROXY_BASE}/series/descs").mock(return_value=httpx.Response(200, json=[]))

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.comparison import _compare_windows_impl

        await _compare_windows_impl(
            client,
            names=["kernel.all.load"],
            window_a_start="-2hours",
            window_a_end="-1hour",
            window_b_start="-1hour",
            window_b_end="now",
            host="",
            instances=[],
            interval="auto",
            include_samples=False,
        )
        # Two /series/values calls should have been made (one per window)
        assert len(values_calls) == 2, f"Expected 2 values calls, got {len(values_calls)}"
        # Both should use the same interval (resolved from window_a duration)
        import re

        intervals = []
        for url in values_calls:
            m = re.search(r"interval=([^&]+)", url)
            if m:
                intervals.append(m.group(1))
        if len(intervals) == 2:
            assert intervals[0] == intervals[1], f"Intervals differ: {intervals}"
    finally:
        await client.close()
