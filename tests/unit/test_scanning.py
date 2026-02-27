"""Unit tests for pcp_scan_changes tool."""

from __future__ import annotations

import httpx
import pytest
import respx

from pmmcp.client import PmproxyClient
from pmmcp.config import PmproxyConfig

PMPROXY_BASE = "http://localhost:44322"
SERIES_A = "aaa0000000000000000000000000000000000001"
SERIES_B = "bbb0000000000000000000000000000000000002"


@pytest.fixture
def config():
    return PmproxyConfig(url=PMPROXY_BASE, timeout=5.0)


def _make_values(series_id: str, values: list[float], base_ts: float = 1547483646.0) -> list[dict]:
    return [
        {"series": series_id, "timestamp": base_ts + i * 60, "value": str(v)}
        for i, v in enumerate(values)
    ]


@respx.mock
async def test_scan_changes_detects_increased_metric(config):
    """pcp_scan_changes returns metrics that increased beyond the ratio threshold."""
    call_count = 0

    def values_side_effect(request):
        nonlocal call_count
        call_count += 1
        # First call = baseline (low), second = comparison (3x higher)
        if call_count == 1:
            return httpx.Response(200, json=_make_values(SERIES_A, [10.0, 10.0, 10.0]))
        return httpx.Response(
            200, json=_make_values(SERIES_A, [30.0, 30.0, 30.0], base_ts=1547570046.0)
        )

    respx.get(f"{PMPROXY_BASE}/series/query").mock(
        return_value=httpx.Response(200, json=[SERIES_A])
    )
    respx.get(f"{PMPROXY_BASE}/series/values").mock(side_effect=values_side_effect)
    respx.get(f"{PMPROXY_BASE}/series/labels").mock(
        return_value=httpx.Response(
            200,
            json=[{"series": SERIES_A, "labels": {"metric.name": "kernel.all.cpu.user"}}],
        )
    )
    respx.get(f"{PMPROXY_BASE}/series/instances").mock(return_value=httpx.Response(200, json=[]))

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.scanning import _scan_changes_impl

        result = await _scan_changes_impl(
            client,
            metric_prefix="kernel",
            baseline_start="-2hours",
            baseline_end="-1hour",
            comparison_start="-1hour",
            comparison_end="now",
            ratio_threshold=1.5,
            max_metrics=50,
            interval="5min",
        )
        assert isinstance(result, dict), f"Expected dict, got: {result}"
        assert "changes" in result
        changes = result["changes"]
        assert len(changes) == 1
        ch = changes[0]
        assert ch["metric"] == "kernel.all.cpu.user"
        assert ch["ratio"] == pytest.approx(3.0)
        assert ch["direction"] == "increased"
        assert result["changed_count"] == 1
        assert result["total_metrics_scanned"] == 1
    finally:
        await client.close()


@respx.mock
async def test_scan_changes_no_change_below_threshold(config):
    """pcp_scan_changes does not flag metrics within the ratio threshold."""
    call_count = 0

    def values_side_effect(request):
        nonlocal call_count
        call_count += 1
        # Baseline and comparison nearly equal (ratio 1.1 < 1.5 threshold)
        if call_count == 1:
            return httpx.Response(200, json=_make_values(SERIES_A, [10.0, 10.0, 10.0]))
        return httpx.Response(200, json=_make_values(SERIES_A, [11.0, 11.0, 11.0]))

    respx.get(f"{PMPROXY_BASE}/series/query").mock(
        return_value=httpx.Response(200, json=[SERIES_A])
    )
    respx.get(f"{PMPROXY_BASE}/series/values").mock(side_effect=values_side_effect)
    respx.get(f"{PMPROXY_BASE}/series/labels").mock(
        return_value=httpx.Response(
            200,
            json=[{"series": SERIES_A, "labels": {"metric.name": "kernel.all.cpu.user"}}],
        )
    )
    respx.get(f"{PMPROXY_BASE}/series/instances").mock(return_value=httpx.Response(200, json=[]))

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.scanning import _scan_changes_impl

        result = await _scan_changes_impl(
            client,
            metric_prefix="kernel",
            baseline_start="-2hours",
            baseline_end="-1hour",
            comparison_start="-1hour",
            comparison_end="now",
            ratio_threshold=1.5,
            max_metrics=50,
            interval="5min",
        )
        assert isinstance(result, dict)
        assert len(result["changes"]) == 0
    finally:
        await client.close()


@respx.mock
async def test_scan_changes_max_metrics_cap(config):
    """pcp_scan_changes respects max_metrics cap."""
    # Two metrics, both changed, but max_metrics=1
    call_count = 0

    def values_side_effect(request):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(
                200,
                json=(_make_values(SERIES_A, [10.0, 10.0]) + _make_values(SERIES_B, [5.0, 5.0])),
            )
        return httpx.Response(
            200,
            json=(_make_values(SERIES_A, [30.0, 30.0]) + _make_values(SERIES_B, [20.0, 20.0])),
        )

    respx.get(f"{PMPROXY_BASE}/series/query").mock(
        return_value=httpx.Response(200, json=[SERIES_A, SERIES_B])
    )
    respx.get(f"{PMPROXY_BASE}/series/values").mock(side_effect=values_side_effect)
    respx.get(f"{PMPROXY_BASE}/series/labels").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"series": SERIES_A, "labels": {"metric.name": "kernel.cpu"}},
                {"series": SERIES_B, "labels": {"metric.name": "kernel.mem"}},
            ],
        )
    )
    respx.get(f"{PMPROXY_BASE}/series/instances").mock(return_value=httpx.Response(200, json=[]))

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.scanning import _scan_changes_impl

        result = await _scan_changes_impl(
            client,
            metric_prefix="kernel",
            baseline_start="-2hours",
            baseline_end="-1hour",
            comparison_start="-1hour",
            comparison_end="now",
            ratio_threshold=1.5,
            max_metrics=1,
            interval="5min",
        )
        assert isinstance(result, dict)
        assert len(result["changes"]) == 1
    finally:
        await client.close()


@respx.mock
async def test_scan_changes_connection_error(config):
    """pcp_scan_changes returns MCP error on connection failure."""
    respx.get(f"{PMPROXY_BASE}/series/query").mock(
        side_effect=httpx.ConnectError("Connection refused")
    )

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.scanning import _scan_changes_impl

        result = await _scan_changes_impl(
            client,
            metric_prefix="kernel",
            baseline_start="-2hours",
            baseline_end="-1hour",
            comparison_start="-1hour",
            comparison_end="now",
            ratio_threshold=1.5,
            max_metrics=50,
            interval="5min",
        )
        assert result.get("isError") is True
    finally:
        await client.close()


@respx.mock
async def test_scan_changes_decreased_metric(config):
    """pcp_scan_changes detects metric that decreased beyond inverse threshold."""
    call_count = 0

    def values_side_effect(request):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(200, json=_make_values(SERIES_A, [30.0, 30.0, 30.0]))
        return httpx.Response(200, json=_make_values(SERIES_A, [10.0, 10.0, 10.0]))

    respx.get(f"{PMPROXY_BASE}/series/query").mock(
        return_value=httpx.Response(200, json=[SERIES_A])
    )
    respx.get(f"{PMPROXY_BASE}/series/values").mock(side_effect=values_side_effect)
    respx.get(f"{PMPROXY_BASE}/series/labels").mock(
        return_value=httpx.Response(
            200,
            json=[{"series": SERIES_A, "labels": {"metric.name": "kernel.all.cpu.user"}}],
        )
    )
    respx.get(f"{PMPROXY_BASE}/series/instances").mock(return_value=httpx.Response(200, json=[]))

    client = PmproxyClient(config)
    try:
        from pmmcp.tools.scanning import _scan_changes_impl

        result = await _scan_changes_impl(
            client,
            metric_prefix="kernel",
            baseline_start="-2hours",
            baseline_end="-1hour",
            comparison_start="-1hour",
            comparison_end="now",
            ratio_threshold=1.5,
            max_metrics=50,
            interval="5min",
        )
        assert isinstance(result, dict)
        changes = result["changes"]
        assert len(changes) == 1
        assert changes[0]["direction"] == "decreased"
        assert changes[0]["ratio"] == pytest.approx(1 / 3, abs=0.01)
    finally:
        await client.close()
