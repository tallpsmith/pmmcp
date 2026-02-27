"""pcp_rank_hosts — rank hosts by metric value with outlier detection."""

from __future__ import annotations

import logging
import math

from pmmcp.client import PmproxyClient, PmproxyConnectionError, PmproxyError, PmproxyTimeoutError
from pmmcp.server import get_client, mcp
from pmmcp.tools._errors import _mcp_error
from pmmcp.tools._stats import _compute_stats, outlier_flag
from pmmcp.utils import expand_time_units, resolve_interval

logger = logging.getLogger(__name__)

_VALID_CRITERIA = {"mean", "p95", "max", "min"}


async def _rank_hosts_impl(
    client: PmproxyClient,
    metric: str,
    start: str,
    end: str,
    criterion: str,
    outlier_threshold: float,
    interval: str,
) -> dict | list:
    """Core implementation, injectable for testing."""
    if criterion not in _VALID_CRITERIA:
        return _mcp_error(
            "Invalid criterion",
            f"criterion must be one of {sorted(_VALID_CRITERIA)}, got {criterion!r}",
            "Use 'mean', 'p95', 'max', or 'min'.",
        )

    resolved = resolve_interval(start, end, interval)

    try:
        series_ids = await client.series_query(metric)
    except PmproxyConnectionError as exc:
        return _mcp_error("Connection error", str(exc), "Check pmproxy connectivity.")
    except PmproxyTimeoutError as exc:
        return _mcp_error("Timeout", str(exc), "Try a smaller time window or fewer metrics.")
    except PmproxyError as exc:
        return _mcp_error("pmproxy error", str(exc), "Check pmproxy logs.")

    if not series_ids:
        return {"metric": metric, "hosts": [], "cluster_summary": {}}

    if isinstance(series_ids[0], dict):
        series_ids = list({entry["series"] for entry in series_ids})

    try:
        raw_values = await client.series_values(
            series=series_ids,
            start=expand_time_units(start),
            finish=expand_time_units(end),
            interval=resolved,
            samples=1000,
        )
    except PmproxyConnectionError as exc:
        return _mcp_error("Connection error", str(exc), "Check pmproxy connectivity.")
    except PmproxyTimeoutError as exc:
        return _mcp_error("Timeout", str(exc), "Try a smaller time window.")
    except PmproxyError as exc:
        return _mcp_error("pmproxy error", str(exc), "Check pmproxy logs.")

    # Get hostname from labels
    hostname_by_series: dict[str, str] = {}
    try:
        labels_list = await client.series_labels(series_ids)
        for item in labels_list:
            labels = item.get("labels", {})
            hostname = labels.get("hostname", labels.get("host", ""))
            if hostname:
                hostname_by_series[item["series"]] = hostname
    except PmproxyError:
        pass

    # Group values by hostname
    values_by_host: dict[str, list[float]] = {}
    for point in raw_values:
        series_id = point["series"]
        hostname = hostname_by_series.get(series_id, series_id[:8])
        try:
            val = float(point["value"])
        except (ValueError, TypeError):
            continue
        values_by_host.setdefault(hostname, []).append(val)

    if not values_by_host:
        return {"metric": metric, "hosts": [], "cluster_summary": {}}

    # Compute stats per host
    host_stats: dict[str, dict] = {}
    for hostname, vals in values_by_host.items():
        host_stats[hostname] = _compute_stats(vals)

    # Cluster-level summary using the criterion values
    hostnames = list(host_stats.keys())
    criterion_values = [host_stats[h][criterion] for h in hostnames]
    n = len(criterion_values)
    cluster_mean = sum(criterion_values) / n if n else 0.0
    cluster_variance = sum((v - cluster_mean) ** 2 for v in criterion_values) / n if n else 0.0
    cluster_stddev = math.sqrt(cluster_variance)

    # Z-scores and outlier flags
    flags = outlier_flag(criterion_values, threshold=outlier_threshold)

    results = []
    for i, hostname in enumerate(hostnames):
        stats = host_stats[hostname]
        crit_val = stats[criterion]
        z_score = (crit_val - cluster_mean) / cluster_stddev if cluster_stddev > 0 else 0.0
        results.append(
            {
                "hostname": hostname,
                "stats": stats,
                "criterion_value": crit_val,
                "z_score": z_score,
                "is_outlier": flags[i],
            }
        )

    # Sort by criterion value descending (highest first)
    results.sort(key=lambda r: r["criterion_value"], reverse=True)

    return {
        "metric": metric,
        "window": {"start": start, "end": end},
        "criterion": criterion,
        "outlier_threshold": outlier_threshold,
        "cluster_summary": {
            "host_count": len(hostnames),
            "cluster_mean": cluster_mean,
            "cluster_stddev": cluster_stddev,
        },
        "hosts": results,
    }


@mcp.tool()
async def pcp_rank_hosts(
    metric: str,
    start: str,
    end: str,
    criterion: str = "mean",
    outlier_threshold: float = 2.0,
    interval: str = "auto",
) -> dict | list:
    """Rank hosts by a metric value and flag statistical outliers.

    Fetches the given metric across all available hosts for the time window,
    computes summary statistics per host, then ranks them by the chosen criterion
    and flags outliers using z-score thresholding.

    Args:
        metric: Metric name to rank hosts by (e.g. 'kernel.all.cpu.user')
        start: Start of the time window (e.g. '-1hour', '-7days')
        end: End of the time window (e.g. 'now', '-30min')
        criterion: Ranking criterion — 'mean', 'p95', 'max', or 'min'
        outlier_threshold: Z-score threshold for outlier detection (default 2.0)
        interval: Sampling interval ('auto' selects based on window duration)
    """
    return await _rank_hosts_impl(
        get_client(),
        metric=metric,
        start=start,
        end=end,
        criterion=criterion,
        outlier_threshold=outlier_threshold,
        interval=interval,
    )
