"""pcp_compare_windows — compare metrics across two time windows with summary statistics."""

from __future__ import annotations

import logging

from pmmcp.client import PmproxyClient, PmproxyConnectionError, PmproxyError, PmproxyTimeoutError
from pmmcp.server import get_client, mcp
from pmmcp.tools._errors import _mcp_error
from pmmcp.tools._fetch import _fetch_window
from pmmcp.tools._stats import _compute_stats
from pmmcp.utils import resolve_interval

logger = logging.getLogger(__name__)


async def _compare_windows_impl(
    client: PmproxyClient,
    names: list[str],
    window_a_start: str,
    window_a_end: str,
    window_b_start: str,
    window_b_end: str,
    host: str,
    instances: list[str],
    interval: str,
    include_samples: bool,
) -> dict | list:
    """Core implementation, injectable for testing."""
    # Resolve interval once using window_a duration
    resolved = resolve_interval(window_a_start, window_a_end, interval)

    # Build expression
    if host:
        parts = [f'{name}{{hostname=="{host}"}}' for name in names]
    else:
        parts = list(names)
    expr = " or ".join(parts) if len(parts) > 1 else parts[0]

    limit = 1000  # fetch up to 1000 points per window for stats

    try:
        values_a, samples_a = await _fetch_window(
            client, expr, window_a_start, window_a_end, resolved, limit
        )
        values_b, samples_b = await _fetch_window(
            client, expr, window_b_start, window_b_end, resolved, limit
        )
    except PmproxyConnectionError as exc:
        return _mcp_error("Connection error", str(exc), "Check pmproxy connectivity.")
    except PmproxyTimeoutError as exc:
        return _mcp_error("Timeout", str(exc), "Try a smaller time window or fewer metrics.")
    except PmproxyError as exc:
        return _mcp_error("pmproxy error", str(exc), "Check pmproxy logs.")

    # Merge keys from both windows
    all_keys = set(values_a.keys()) | set(values_b.keys())
    comparisons = []

    for key in sorted(all_keys, key=lambda k: (k[0], k[1] or "")):
        metric_name, instance_name = key

        # Apply instance filter
        if instances and instance_name and instance_name not in instances:
            continue

        va = values_a.get(key, [])
        vb = values_b.get(key, [])

        stats_a = _compute_stats(va)
        stats_b = _compute_stats(vb)

        mean_change = stats_b["mean"] - stats_a["mean"]
        mean_change_pct = (mean_change / stats_a["mean"] * 100) if stats_a["mean"] != 0 else 0.0
        stddev_change = stats_b["stddev"] - stats_a["stddev"]
        # Significant: |mean_change| > 2 * window_a.stddev
        significant = abs(mean_change) > 2 * stats_a["stddev"] if stats_a["stddev"] > 0 else False

        comp: dict = {
            "metric": metric_name,
            "instance": instance_name,
            "window_a": stats_a,
            "window_b": stats_b,
            "delta": {
                "mean_change": mean_change,
                "mean_change_pct": mean_change_pct,
                "stddev_change": stddev_change,
                "significant": significant,
            },
        }

        if include_samples:
            comp["window_a_samples"] = samples_a.get(key, [])
            comp["window_b_samples"] = samples_b.get(key, [])

        comparisons.append(comp)

    return comparisons


@mcp.tool()
async def pcp_compare_windows(
    names: list[str],
    window_a_start: str,
    window_a_end: str,
    window_b_start: str,
    window_b_end: str,
    host: str = "",
    instances: list[str] = [],  # noqa: B006
    interval: str = "auto",
    include_samples: bool = False,
) -> dict | list:
    """Fetch the same metrics over two time windows and return summary statistics with deltas.

    Designed for 'good period vs bad period' comparison. Returns mean, min, max, p95, stddev
    for each window with absolute/percentage deltas and a significance flag (> 2 stddev).

    Args:
        names: List of metric names to compare
        window_a_start: Start of first (baseline/good) window
        window_a_end: End of first window
        window_b_start: Start of second (comparison/bad) window
        window_b_end: End of second window
        host: Target hostname
        instances: Filter to specific instances (empty means all)
        interval: Sampling interval for both windows ('auto' selects based on window_a duration)
        include_samples: If True, include raw sample data alongside summary stats
    """
    return await _compare_windows_impl(
        get_client(),
        names=names,
        window_a_start=window_a_start,
        window_a_end=window_a_end,
        window_b_start=window_b_start,
        window_b_end=window_b_end,
        host=host,
        instances=instances,
        interval=interval,
        include_samples=include_samples,
    )
