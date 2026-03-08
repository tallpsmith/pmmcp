"""pcp_correlate_metrics — Pearson correlation between multiple metrics."""

from __future__ import annotations

import logging
from itertools import combinations

from pmmcp.client import PmproxyClient, PmproxyConnectionError, PmproxyError, PmproxyTimeoutError
from pmmcp.server import get_client, mcp
from pmmcp.tools._errors import _mcp_error
from pmmcp.tools._expr import build_series_expr
from pmmcp.tools._fetch import _fetch_window
from pmmcp.tools._stats import pearson_correlation
from pmmcp.utils import resolve_interval

logger = logging.getLogger(__name__)


def _classify_correlation(r: float) -> str:
    """Classify Pearson r into a human-readable strength label."""
    abs_r = abs(r)
    if abs_r >= 0.9:
        return "very strong"
    elif abs_r >= 0.7:
        return "strong"
    elif abs_r >= 0.5:
        return "moderate"
    elif abs_r >= 0.3:
        return "weak"
    else:
        return "negligible"


def _align_series(vals_a: list[float], vals_b: list[float]) -> tuple[list[float], list[float]]:
    """Align two series to the same length by truncating the longer one."""
    n = min(len(vals_a), len(vals_b))
    return vals_a[:n], vals_b[:n]


async def _correlate_metrics_impl(
    client: PmproxyClient,
    metrics: list[str],
    start: str,
    end: str,
    host: str,
    interval: str,
) -> dict | list:
    """Core implementation, injectable for testing."""
    if len(metrics) < 2:
        return _mcp_error(
            "Insufficient metrics",
            "At least 2 metrics are required for correlation analysis.",
            "Provide 2 or more metric names.",
        )

    resolved = resolve_interval(start, end, interval)

    expr = build_series_expr(metrics, host=host)

    try:
        values_by_key, _ = await _fetch_window(
            client, exprs=[expr], start=start, end=end, interval=resolved, limit=1000,
        )
    except PmproxyConnectionError as exc:
        return _mcp_error("Connection error", str(exc), "Check pmproxy connectivity.")
    except PmproxyTimeoutError as exc:
        return _mcp_error("Timeout", str(exc), "Try a smaller time window or fewer metrics.")
    except PmproxyError as exc:
        return _mcp_error("pmproxy error", str(exc), "Check pmproxy logs.")

    # Aggregate values per metric (across instances)
    metric_values: dict[str, list[float]] = {}
    for (metric_name, _instance), vals in values_by_key.items():
        metric_values.setdefault(metric_name, []).extend(vals)

    # Compute pairwise Pearson correlations
    pairs = []
    metric_list = sorted(metric_values.keys())
    for m_a, m_b in combinations(metric_list, 2):
        vals_a, vals_b = _align_series(metric_values[m_a], metric_values[m_b])
        r = pearson_correlation(vals_a, vals_b)
        strength = _classify_correlation(r)
        direction = "positive" if r >= 0 else "negative"
        pairs.append(
            {
                "metric_a": m_a,
                "metric_b": m_b,
                "r": r,
                "strength": strength,
                "direction": direction,
                "interpretation": (
                    f"{m_a} and {m_b} have a {strength} {direction} correlation (r={r:.3f})"
                ),
            }
        )

    # Sort by |r| descending
    pairs.sort(key=lambda p: abs(p["r"]), reverse=True)

    return {
        "window": {"start": start, "end": end},
        "host": host or "all",
        "metrics_found": metric_list,
        "correlations": pairs,
    }


@mcp.tool()
async def pcp_correlate_metrics(
    metrics: list[str],
    start: str,
    end: str,
    host: str = "",
    interval: str = "auto",
) -> dict | list:
    """Compute pairwise Pearson correlations between two or more metrics.

    Fetches time-series data for all specified metrics over the given window,
    aligns the samples, and computes the Pearson r between every pair.

    Args:
        metrics: List of 2 or more metric names to correlate
        start: Start of the time window (e.g. '-1hour')
        end: End of the time window (e.g. 'now')
        host: Target hostname (empty means all)
        interval: Sampling interval ('auto' selects based on window duration)
    """
    return await _correlate_metrics_impl(
        get_client(),
        metrics=metrics,
        start=start,
        end=end,
        host=host,
        interval=interval,
    )
