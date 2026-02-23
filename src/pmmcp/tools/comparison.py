"""pcp_compare_windows — compare metrics across two time windows with summary statistics."""

from __future__ import annotations

import logging
import math

from pmmcp.client import PmproxyClient, PmproxyConnectionError, PmproxyError, PmproxyTimeoutError
from pmmcp.server import get_client, mcp
from pmmcp.utils import resolve_interval

logger = logging.getLogger(__name__)


def _mcp_error(category: str, description: str, suggestion: str) -> dict:
    text = f"Error: {category}\n\nDetails: {description}\nSuggestion: {suggestion}"
    return {"content": [{"type": "text", "text": text}], "isError": True}


def _compute_stats(values: list[float]) -> dict:
    """Compute WindowStats for a list of numeric values."""
    n = len(values)
    if n == 0:
        return {"mean": 0.0, "min": 0.0, "max": 0.0, "p95": 0.0, "stddev": 0.0, "sample_count": 0}

    mean = sum(values) / n
    minimum = min(values)
    maximum = max(values)

    # p95 via sorted percentile
    sorted_vals = sorted(values)
    p95_idx = max(0, int(math.ceil(0.95 * n)) - 1)
    p95 = sorted_vals[p95_idx]

    variance = sum((v - mean) ** 2 for v in values) / n
    stddev = math.sqrt(variance)

    return {
        "mean": mean,
        "min": minimum,
        "max": maximum,
        "p95": p95,
        "stddev": stddev,
        "sample_count": n,
    }


async def _fetch_window(
    client: PmproxyClient,
    expr: str,
    start: str,
    end: str,
    interval: str,
    limit: int,
) -> tuple[dict[tuple[str, str | None], list[float]], dict[tuple[str, str | None], list[dict]]]:
    """Fetch a window and return (numeric_values_by_key, raw_samples_by_key)."""
    try:
        series_ids = await client.series_query(expr)
    except (PmproxyConnectionError, PmproxyTimeoutError, PmproxyError):
        raise

    if not series_ids:
        return {}, {}

    if isinstance(series_ids[0], dict):
        series_ids = list({entry["series"] for entry in series_ids})

    try:
        raw_values = await client.series_values(
            series=series_ids, start=start, finish=end, interval=interval, samples=limit
        )
    except (PmproxyConnectionError, PmproxyTimeoutError, PmproxyError):
        raise

    # Get metric names for series IDs
    name_by_series: dict[str, str] = {}
    try:
        labels_list = await client.series_labels(series_ids)
        for item in labels_list:
            metric_name = item.get("labels", {}).get("metric.name", "")
            if metric_name:
                name_by_series[item["series"]] = metric_name
    except PmproxyError:
        pass

    # Get instance names
    instance_name_by_series: dict[str, str] = {}
    try:
        instances_list = await client.series_instances(series_ids)
        for item in instances_list:
            instance_name_by_series[item["series"]] = item.get("name", "")
    except PmproxyError:
        pass

    numeric_values: dict[tuple[str, str | None], list[float]] = {}
    raw_samples: dict[tuple[str, str | None], list[dict]] = {}

    for point in raw_values:
        series_id = point["series"]
        metric_name = name_by_series.get(series_id, series_id)
        instance_name = instance_name_by_series.get(series_id) or None
        key = (metric_name, instance_name)

        try:
            numeric_val = float(point["value"])
        except (ValueError, TypeError):
            continue

        if key not in numeric_values:
            numeric_values[key] = []
            raw_samples[key] = []
        numeric_values[key].append(numeric_val)
        raw_samples[key].append({"timestamp": point["timestamp"], "value": numeric_val})

    return numeric_values, raw_samples


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
