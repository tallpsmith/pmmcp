"""Unit tests for pcp_quick_investigate tool (US1 — T002-T007)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from pmmcp.tools.investigate import _quick_investigate_impl

# ── Helpers ──────────────────────────────────────────────────────────────────

FIXED_NOW = datetime(2025, 1, 15, 14, 0, 0, tzinfo=UTC)
FIXED_NOW_ISO = "2025-01-15T14:00:00+00:00"
ONE_HOUR_AGO_ISO = "2025-01-15T13:00:00+00:00"


def _make_anomaly(metric: str, instance: str, z_score: float, direction: str = "increasing"):
    """Build a fake anomaly dict matching _detect_anomalies_impl output."""
    return {
        "metric": metric,
        "instance": instance,
        "severity": "high" if abs(z_score) > 4 else ("medium" if abs(z_score) > 3 else "low"),
        "z_score": z_score,
        "direction": direction,
        "recent": {"mean": 10.0, "min": 5.0, "max": 15.0, "p95": 14.0, "stddev": 2.0, "count": 10},
        "baseline": {"mean": 5.0, "min": 2.0, "max": 8.0, "p95": 7.0, "stddev": 1.0, "count": 100},
        "interpretation": f"{metric} is {direction} (z={z_score:.2f})",
    }


def _make_discovery_result(metric_names: list[str]) -> dict:
    """Build a fake discovery result matching _discover_metrics_impl output."""
    return {
        "items": [{"name": n, "oneline": "", "leaf": True} for n in metric_names],
        "total": len(metric_names),
        "limit": 50,
        "offset": 0,
        "has_more": False,
    }


# ── T002: Basic invocation returns ranked anomaly list ───────────────────────


@pytest.mark.asyncio
async def test_basic_invocation_returns_ranked_anomaly_list():
    """Call with only time_of_interest; verify InvestigationResult structure."""
    discovered_metrics = ["kernel.all.load", "mem.util.used"]
    anomalies = [
        _make_anomaly("kernel.all.load", "1 minute", 3.5, "increasing"),
        _make_anomaly("mem.util.used", "", 2.8, "increasing"),
    ]

    client = AsyncMock()

    with (
        patch(
            "pmmcp.tools.investigate._discover_metrics_impl",
            new_callable=AsyncMock,
            return_value=_make_discovery_result(discovered_metrics),
        ),
        patch(
            "pmmcp.tools.investigate._detect_anomalies_impl",
            new_callable=AsyncMock,
            return_value=anomalies,
        ),
    ):
        result = await _quick_investigate_impl(client, time_of_interest=ONE_HOUR_AGO_ISO)

    assert "anomalies" in result
    assert "metadata" in result
    assert "message" in result
    assert "truncated" in result
    assert isinstance(result["anomalies"], list)
    assert len(result["anomalies"]) == 2

    # Verify anomaly item structure
    item = result["anomalies"][0]
    assert "metric" in item
    assert "instance" in item
    assert "score" in item
    assert "severity" in item
    assert "direction" in item
    assert "magnitude" in item
    assert "summary" in item

    # Score must be absolute (positive)
    for a in result["anomalies"]:
        assert a["score"] >= 0

    # Must be sorted by score descending
    scores = [a["score"] for a in result["anomalies"]]
    assert scores == sorted(scores, reverse=True)


# ── T003: Time window computation ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_time_window_computation_defaults():
    """Recent window centred on time_of_interest, baseline ends where recent starts."""
    client = AsyncMock()
    captured_args = {}

    async def capture_detect(client, **kwargs):
        captured_args.update(kwargs)
        return []

    with (
        patch(
            "pmmcp.tools.investigate._discover_metrics_impl",
            new_callable=AsyncMock,
            return_value=_make_discovery_result(["kernel.all.load"]),
        ),
        patch(
            "pmmcp.tools.investigate._detect_anomalies_impl",
            side_effect=capture_detect,
        ),
    ):
        await _quick_investigate_impl(client, time_of_interest=FIXED_NOW_ISO)

    # Default lookback is 2hours => half is 1 hour
    # recent_start = time_of_interest - 1h = 13:00
    # recent_end = time_of_interest + 1h = 15:00
    # baseline_start = recent_start - 7 days
    # baseline_end = recent_start
    assert "recent_start" in captured_args
    assert "recent_end" in captured_args
    assert "baseline_start" in captured_args
    assert "baseline_end" in captured_args

    from pmmcp.utils import parse_time_expr

    recent_start = parse_time_expr(captured_args["recent_start"])
    recent_end = parse_time_expr(captured_args["recent_end"])
    baseline_end = parse_time_expr(captured_args["baseline_end"])
    baseline_start = parse_time_expr(captured_args["baseline_start"])

    # Recent window centred on FIXED_NOW with 2h lookback => 1h each side
    assert recent_start == FIXED_NOW - timedelta(hours=1)
    assert recent_end == FIXED_NOW + timedelta(hours=1)

    # Baseline ends where recent starts
    assert baseline_end == recent_start

    # Baseline is 7 days long
    assert baseline_start == recent_start - timedelta(days=7)


# ── T004: Empty anomalies returns "No anomalies detected" ───────────────────


@pytest.mark.asyncio
async def test_empty_anomalies_returns_no_anomalies_message():
    """When no anomalies detected, message should say so."""
    client = AsyncMock()

    with (
        patch(
            "pmmcp.tools.investigate._discover_metrics_impl",
            new_callable=AsyncMock,
            return_value=_make_discovery_result(["kernel.all.load"]),
        ),
        patch(
            "pmmcp.tools.investigate._detect_anomalies_impl",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        result = await _quick_investigate_impl(client, time_of_interest=ONE_HOUR_AGO_ISO)

    assert result["anomalies"] == []
    assert "No anomalies detected" in result["message"]
    assert result["truncated"] is False


# ── T005: Future time_of_interest raises validation error ────────────────────


@pytest.mark.asyncio
async def test_future_time_of_interest_returns_error():
    """A time_of_interest in the future must return an MCP error."""
    client = AsyncMock()
    future_time = (datetime.now(tz=UTC) + timedelta(hours=2)).isoformat()

    result = await _quick_investigate_impl(client, time_of_interest=future_time)

    assert result["isError"] is True
    assert "must be in the past" in result["content"][0]["text"]


# ── T006: Results capped at 50, sorted by score desc, truncated=true ────────


@pytest.mark.asyncio
async def test_results_capped_at_50_sorted_truncated():
    """More than 50 anomalies → capped at 50, sorted by score desc, truncated=true."""
    client = AsyncMock()

    # Create 60 anomalies with varying z-scores
    anomalies = [_make_anomaly(f"metric.{i}", "", float(i + 1), "increasing") for i in range(60)]

    with (
        patch(
            "pmmcp.tools.investigate._discover_metrics_impl",
            new_callable=AsyncMock,
            return_value=_make_discovery_result([f"metric.{i}" for i in range(60)]),
        ),
        patch(
            "pmmcp.tools.investigate._detect_anomalies_impl",
            new_callable=AsyncMock,
            return_value=anomalies,
        ),
    ):
        result = await _quick_investigate_impl(client, time_of_interest=ONE_HOUR_AGO_ISO)

    assert len(result["anomalies"]) == 50
    assert result["truncated"] is True

    # Sorted by score descending
    scores = [a["score"] for a in result["anomalies"]]
    assert scores == sorted(scores, reverse=True)

    # Highest score should be first
    assert scores[0] == 60.0


# ── T007: No metrics discovered triggers MCP error ──────────────────────────


@pytest.mark.asyncio
async def test_no_metrics_discovered_returns_error():
    """When discovery returns no metrics, should return _mcp_error."""
    client = AsyncMock()

    with patch(
        "pmmcp.tools.investigate._discover_metrics_impl",
        new_callable=AsyncMock,
        return_value=_make_discovery_result([]),
    ):
        result = await _quick_investigate_impl(client, time_of_interest=ONE_HOUR_AGO_ISO)

    assert result["isError"] is True
    assert "No metrics found" in result["content"][0]["text"]


# ── T021: subsystem scopes discovery to prefix ──────────────────────────────


@pytest.mark.asyncio
async def test_subsystem_scopes_discovery_to_prefix():
    """subsystem='disk' passes prefix='disk' to discovery."""
    client = AsyncMock()
    captured_discovery_args = {}

    async def capture_discover(client, **kwargs):
        captured_discovery_args.update(kwargs)
        return _make_discovery_result(["disk.dev.read", "disk.dev.write"])

    with (
        patch(
            "pmmcp.tools.investigate._discover_metrics_impl",
            side_effect=capture_discover,
        ),
        patch(
            "pmmcp.tools.investigate._detect_anomalies_impl",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        await _quick_investigate_impl(client, time_of_interest=ONE_HOUR_AGO_ISO, subsystem="disk")

    assert captured_discovery_args["prefix"] == "disk"


# ── T022: custom lookback adjusts recent window ────────────────────────────


@pytest.mark.asyncio
async def test_custom_lookback_adjusts_recent_window():
    """lookback='30minutes' → half is 15min each side of time_of_interest."""
    client = AsyncMock()
    captured_args = {}

    async def capture_detect(client, **kwargs):
        captured_args.update(kwargs)
        return []

    with (
        patch(
            "pmmcp.tools.investigate._discover_metrics_impl",
            new_callable=AsyncMock,
            return_value=_make_discovery_result(["kernel.all.load"]),
        ),
        patch(
            "pmmcp.tools.investigate._detect_anomalies_impl",
            side_effect=capture_detect,
        ),
    ):
        await _quick_investigate_impl(client, time_of_interest=FIXED_NOW_ISO, lookback="30minutes")

    from pmmcp.utils import parse_time_expr

    recent_start = parse_time_expr(captured_args["recent_start"])
    recent_end = parse_time_expr(captured_args["recent_end"])

    # 30 minutes lookback → 15 min each side
    assert recent_start == FIXED_NOW - timedelta(minutes=15)
    assert recent_end == FIXED_NOW + timedelta(minutes=15)


# ── T023: custom baseline_days extends baseline window ──────────────────────


@pytest.mark.asyncio
async def test_custom_baseline_days_extends_baseline():
    """baseline_days=14 → baseline is 14 days long."""
    client = AsyncMock()
    captured_args = {}

    async def capture_detect(client, **kwargs):
        captured_args.update(kwargs)
        return []

    with (
        patch(
            "pmmcp.tools.investigate._discover_metrics_impl",
            new_callable=AsyncMock,
            return_value=_make_discovery_result(["kernel.all.load"]),
        ),
        patch(
            "pmmcp.tools.investigate._detect_anomalies_impl",
            side_effect=capture_detect,
        ),
    ):
        await _quick_investigate_impl(client, time_of_interest=FIXED_NOW_ISO, baseline_days=14)

    from pmmcp.utils import parse_time_expr

    baseline_start = parse_time_expr(captured_args["baseline_start"])
    baseline_end = parse_time_expr(captured_args["baseline_end"])

    # baseline is 14 days long
    assert (baseline_end - baseline_start).days == 14


# ── T024: host parameter passes through ────────────────────────────────────


@pytest.mark.asyncio
async def test_host_passes_through_to_discovery_and_anomaly():
    """host parameter is forwarded to both discovery and anomaly detection."""
    client = AsyncMock()
    discovery_host = None
    detect_host = None

    async def capture_discover(client, **kwargs):
        nonlocal discovery_host
        discovery_host = kwargs.get("host")
        return _make_discovery_result(["kernel.all.load"])

    async def capture_detect(client, **kwargs):
        nonlocal detect_host
        detect_host = kwargs.get("host")
        return []

    with (
        patch(
            "pmmcp.tools.investigate._discover_metrics_impl",
            side_effect=capture_discover,
        ),
        patch(
            "pmmcp.tools.investigate._detect_anomalies_impl",
            side_effect=capture_detect,
        ),
    ):
        await _quick_investigate_impl(client, time_of_interest=ONE_HOUR_AGO_ISO, host="web-01")

    assert discovery_host == "web-01"
    assert detect_host == "web-01"
