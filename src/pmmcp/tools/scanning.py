"""pcp_scan_changes — brute-force change detection across metric namespace."""

from __future__ import annotations

import logging

from pmmcp.client import PmproxyClient, PmproxyConnectionError, PmproxyError, PmproxyTimeoutError
from pmmcp.server import get_client, mcp
from pmmcp.tools._errors import _mcp_error
from pmmcp.tools._fetch import _fetch_window, _resolve_series_ids
from pmmcp.tools._stats import _compute_stats
from pmmcp.utils import resolve_interval

logger = logging.getLogger(__name__)


async def _scan_changes_impl(
    client: PmproxyClient,
    metric_prefix: str,
    baseline_start: str,
    baseline_end: str,
    comparison_start: str,
    comparison_end: str,
    ratio_threshold: float,
    max_metrics: int,
    interval: str,
) -> dict | list:
    """Core implementation, injectable for testing."""
    resolved = resolve_interval(baseline_start, baseline_end, interval)

    # Build wildcard expression for the prefix
    if metric_prefix.endswith("*"):
        expr = metric_prefix
    else:
        expr = f"{metric_prefix}.*"

    try:
        series_ids = await _resolve_series_ids(client, [expr])
        baseline_vals, _ = await _fetch_window(
            client,
            exprs=[],
            start=baseline_start,
            end=baseline_end,
            interval=resolved,
            limit=500,
            series_ids=series_ids,
        )
        comparison_vals, _ = await _fetch_window(
            client,
            exprs=[],
            start=comparison_start,
            end=comparison_end,
            interval=resolved,
            limit=500,
            series_ids=series_ids,
        )
    except PmproxyConnectionError as exc:
        return _mcp_error("Connection error", str(exc), "Check pmproxy connectivity.")
    except PmproxyTimeoutError as exc:
        return _mcp_error("Timeout", str(exc), "Try a smaller time window or narrower prefix.")
    except PmproxyError as exc:
        return _mcp_error("pmproxy error", str(exc), "Check pmproxy logs.")

    all_keys = set(baseline_vals.keys()) | set(comparison_vals.keys())
    changed = []

    for key in all_keys:
        metric_name, instance_name = key
        bvals = baseline_vals.get(key, [])
        cvals = comparison_vals.get(key, [])

        bstats = _compute_stats(bvals)
        cstats = _compute_stats(cvals)

        b_mean = bstats["mean"]
        c_mean = cstats["mean"]

        if b_mean == 0.0:
            ratio = float("inf") if c_mean != 0.0 else 1.0
        else:
            ratio = c_mean / b_mean

        # Flag if increased by >= ratio_threshold or decreased to <= 1/ratio_threshold
        is_changed = ratio >= ratio_threshold or (
            ratio_threshold > 0 and ratio <= 1.0 / ratio_threshold
        )

        if is_changed:
            magnitude = abs(ratio - 1.0)
            changed.append(
                {
                    "metric": metric_name,
                    "instance": instance_name,
                    "baseline_mean": b_mean,
                    "comparison_mean": c_mean,
                    "ratio": ratio,
                    "magnitude": magnitude,
                    "direction": "increased" if c_mean > b_mean else "decreased",
                    "baseline_stats": bstats,
                    "comparison_stats": cstats,
                }
            )

    # Sort by magnitude descending, then apply cap
    changed.sort(key=lambda x: x["magnitude"], reverse=True)
    changed = changed[:max_metrics]

    return {
        "metric_prefix": metric_prefix,
        "baseline": {"start": baseline_start, "end": baseline_end},
        "comparison": {"start": comparison_start, "end": comparison_end},
        "ratio_threshold": ratio_threshold,
        "total_metrics_scanned": len(all_keys),
        "changed_count": len(changed),
        "changes": changed,
    }


@mcp.tool()
async def pcp_scan_changes(
    metric_prefix: str,
    baseline_start: str,
    baseline_end: str,
    comparison_start: str,
    comparison_end: str,
    ratio_threshold: float = 1.5,
    max_metrics: int = 50,
    interval: str = "auto",
) -> dict | list:
    """Scan a metric namespace for significant changes between two time windows.

    For scanning broad changes in a metric prefix. For discovery, start with
    pcp_quick_investigate. Inspired by pmdiff — discovers all metrics under a
    prefix, fetches both windows, and returns those whose mean changed by more
    than ratio_threshold.

    Args:
        metric_prefix: Metric namespace prefix to scan (e.g. 'kernel', 'mem')
        baseline_start: Start of the baseline window
        baseline_end: End of the baseline window
        comparison_start: Start of the comparison window
        comparison_end: End of the comparison window
        ratio_threshold: Ratio of comparison/baseline mean to flag as changed (default 1.5)
        max_metrics: Maximum number of changed metrics to return (default 50).
            For exploration use 50; increase to 200+ for full scan.
        interval: Sampling interval ('auto' selects based on baseline window duration)

    Note: For broad investigations, start with the ``coordinate_investigation`` prompt
    rather than scanning changes directly — it orchestrates a full multi-subsystem sweep.
    """
    return await _scan_changes_impl(
        get_client(),
        metric_prefix=metric_prefix,
        baseline_start=baseline_start,
        baseline_end=baseline_end,
        comparison_start=comparison_start,
        comparison_end=comparison_end,
        ratio_threshold=ratio_threshold,
        max_metrics=max_metrics,
        interval=interval,
    )
