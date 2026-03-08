"""pcp_detect_anomalies — detect temporal baseline deviation."""

from __future__ import annotations

import logging

from pmmcp.client import PmproxyClient, PmproxyConnectionError, PmproxyError, PmproxyTimeoutError
from pmmcp.server import get_client, mcp
from pmmcp.tools._errors import _mcp_error
from pmmcp.tools._expr import build_series_exprs
from pmmcp.tools._fetch import _fetch_window, _resolve_series_ids
from pmmcp.tools._stats import _compute_stats
from pmmcp.utils import resolve_interval

logger = logging.getLogger(__name__)


def _severity(z_score: float, threshold: float) -> str:
    """Classify anomaly severity based on z-score relative to threshold."""
    abs_z = abs(z_score)
    if abs_z < threshold:
        return "none"
    elif abs_z < threshold * 1.5:
        return "low"
    elif abs_z < threshold * 2.0:
        return "medium"
    else:
        return "high"


async def _detect_anomalies_impl(
    client: PmproxyClient,
    metrics: list[str],
    recent_start: str,
    recent_end: str,
    baseline_start: str,
    baseline_end: str,
    z_score_threshold: float,
    host: str,
    interval: str,
) -> dict | list:
    """Core implementation, injectable for testing."""
    resolved = resolve_interval(baseline_start, baseline_end, interval)

    exprs = build_series_exprs(metrics, host=host)

    try:
        series_ids = await _resolve_series_ids(client, exprs)
        baseline_vals, _ = await _fetch_window(
            client, exprs=[], start=baseline_start, end=baseline_end,
            interval=resolved, limit=1000, series_ids=series_ids,
        )
        recent_vals, _ = await _fetch_window(
            client, exprs=[], start=recent_start, end=recent_end,
            interval=resolved, limit=200, series_ids=series_ids,
        )
    except PmproxyConnectionError as exc:
        return _mcp_error("Connection error", str(exc), "Check pmproxy connectivity.")
    except PmproxyTimeoutError as exc:
        return _mcp_error("Timeout", str(exc), "Try a smaller time window or fewer metrics.")
    except PmproxyError as exc:
        return _mcp_error("pmproxy error", str(exc), "Check pmproxy logs.")

    all_keys = set(baseline_vals.keys()) | set(recent_vals.keys())
    anomalies = []

    for key in sorted(all_keys, key=lambda k: (k[0], k[1] or "")):
        metric_name, instance_name = key
        bvals = baseline_vals.get(key, [])
        rvals = recent_vals.get(key, [])

        baseline_stats = _compute_stats(bvals)
        recent_stats = _compute_stats(rvals)

        # Z-score: how far is recent mean from baseline distribution?
        if baseline_stats["stddev"] > 0:
            z = (recent_stats["mean"] - baseline_stats["mean"]) / baseline_stats["stddev"]
        else:
            z = 0.0

        sev = _severity(z, z_score_threshold)

        if recent_stats["mean"] > baseline_stats["mean"]:
            direction = "increasing"
        elif recent_stats["mean"] < baseline_stats["mean"]:
            direction = "decreasing"
        else:
            direction = "stable"

        anomalies.append(
            {
                "metric": metric_name,
                "instance": instance_name,
                "severity": sev,
                "z_score": z,
                "direction": direction,
                "recent": recent_stats,
                "baseline": baseline_stats,
                "interpretation": (f"{metric_name} is {direction} (z={z:.2f}, severity={sev})"),
            }
        )

    return anomalies


@mcp.tool()
async def pcp_detect_anomalies(
    metrics: list[str],
    recent_start: str,
    recent_end: str,
    baseline_start: str,
    baseline_end: str,
    z_score_threshold: float = 2.0,
    host: str = "",
    interval: str = "auto",
) -> dict | list:
    """Detect anomalies by comparing recent metric behavior to a historical baseline.

    For targeted anomaly analysis on known metrics. For discovery, start with
    pcp_quick_investigate. Fetches each metric over two windows — a short recent
    window and a longer historical baseline — then computes a z-score to quantify
    how far the recent behavior deviates from the baseline distribution.

    Args:
        metrics: List of metric names to analyse
        recent_start: Start of the recent (comparison) window
        recent_end: End of the recent window (typically 'now')
        baseline_start: Start of the historical baseline window
        baseline_end: End of the baseline window
        z_score_threshold: Z-score above which a deviation is anomalous (default 2.0)
        host: Target hostname (empty means all hosts)
        interval: Sampling interval ('auto' selects based on baseline window duration)
    """
    return await _detect_anomalies_impl(
        get_client(),
        metrics=metrics,
        recent_start=recent_start,
        recent_end=recent_end,
        baseline_start=baseline_start,
        baseline_end=baseline_end,
        z_score_threshold=z_score_threshold,
        host=host,
        interval=interval,
    )
