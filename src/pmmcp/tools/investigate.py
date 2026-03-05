"""pcp_quick_investigate — low-friction open-ended investigation entry point."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from pmmcp.client import PmproxyClient
from pmmcp.server import get_client, mcp
from pmmcp.tools._errors import _mcp_error
from pmmcp.tools.anomaly import _detect_anomalies_impl
from pmmcp.tools.discovery import _discover_metrics_impl
from pmmcp.utils import parse_time_expr

logger = logging.getLogger(__name__)

MAX_RESULTS = 50


def _parse_lookback_to_timedelta(lookback: str) -> timedelta:
    """Convert a PCP time expression like '2hours' or '30minutes' to timedelta."""
    from pmmcp.utils import interval_to_seconds

    secs = interval_to_seconds(lookback)
    return timedelta(seconds=secs)


def _severity_from_zscore(z: float) -> str:
    """Classify anomaly severity from absolute z-score."""
    abs_z = abs(z)
    if abs_z > 4:
        return "high"
    elif abs_z > 3:
        return "medium"
    else:
        return "low"


def _direction_label(direction: str) -> str:
    """Normalise anomaly direction to 'up' or 'down'."""
    if direction in ("increasing",):
        return "up"
    elif direction in ("decreasing",):
        return "down"
    return "up"


async def _quick_investigate_impl(
    client: PmproxyClient,
    time_of_interest: str,
    subsystem: str = "",
    lookback: str = "2hours",
    baseline_days: int = 7,
    host: str = "",
) -> dict:
    """Core implementation — orchestrate discovery + anomaly detection.

    Returns an InvestigationResult dict or an MCP error dict.
    """
    # Validate time_of_interest is in the past
    try:
        toi = parse_time_expr(time_of_interest)
    except (ValueError, TypeError) as exc:
        return _mcp_error(
            "Validation error",
            f"Cannot parse time_of_interest: {exc}",
            "Provide an ISO-8601 datetime or PCP relative expression like '-2hours'.",
        )

    if toi > datetime.now(tz=UTC):
        return _mcp_error(
            "Validation error",
            "time_of_interest must be in the past",
            "Provide a historical timestamp to investigate.",
        )

    # Compute time windows
    half_lookback = _parse_lookback_to_timedelta(lookback) / 2
    recent_start = toi - half_lookback
    recent_end = toi + half_lookback
    baseline_start = recent_start - timedelta(days=baseline_days)
    baseline_end = recent_start

    # Format as ISO strings
    recent_start_str = recent_start.isoformat()
    recent_end_str = recent_end.isoformat()
    baseline_start_str = baseline_start.isoformat()
    baseline_end_str = baseline_end.isoformat()

    # Discover metrics
    discovery = await _discover_metrics_impl(
        client, host=host, prefix=subsystem, search="", limit=200, offset=0
    )

    if isinstance(discovery, dict) and discovery.get("isError"):
        return discovery

    items = discovery.get("items", [])
    metric_names = [item["name"] for item in items if item.get("leaf", True)]

    if not metric_names:
        prefix_msg = f" for prefix '{subsystem}'" if subsystem else ""
        return _mcp_error(
            "No metrics found",
            f"No metrics discovered{prefix_msg}",
            "Check the subsystem name or omit it to search all metrics.",
        )

    # Run anomaly detection
    raw_anomalies = await _detect_anomalies_impl(
        client,
        metrics=metric_names,
        recent_start=recent_start_str,
        recent_end=recent_end_str,
        baseline_start=baseline_start_str,
        baseline_end=baseline_end_str,
        z_score_threshold=2.0,
        host=host,
        interval="auto",
    )

    # If anomaly detection returned an error, propagate it
    if isinstance(raw_anomalies, dict) and raw_anomalies.get("isError"):
        return raw_anomalies

    # Filter to actual anomalies (severity != "none") and transform to output format
    anomaly_items = []
    for a in raw_anomalies:
        if a.get("severity") == "none":
            continue

        z = a["z_score"]
        recent_mean = a["recent"]["mean"]
        baseline_mean = a["baseline"]["mean"]
        magnitude = abs(recent_mean - baseline_mean)
        direction = _direction_label(a["direction"])
        severity = _severity_from_zscore(z)
        score = abs(z)

        anomaly_items.append(
            {
                "metric": a["metric"],
                "instance": a["instance"] or "",
                "score": score,
                "severity": severity,
                "direction": direction,
                "magnitude": magnitude,
                "summary": (
                    f"{a['metric']} is {score:.1f}\u03c3"
                    f" {'above' if direction == 'up' else 'below'}"
                    f" baseline mean"
                    f" ({baseline_mean:.1f} \u2192 {recent_mean:.1f})"
                ),
            }
        )

    # Sort by score descending and cap
    anomaly_items.sort(key=lambda x: x["score"], reverse=True)
    truncated = len(anomaly_items) > MAX_RESULTS
    anomaly_items = anomaly_items[:MAX_RESULTS]

    metrics_examined = len(metric_names)
    if anomaly_items:
        message = f"Found {len(anomaly_items)} anomalies across {metrics_examined} metrics examined"
    else:
        message = f"No anomalies detected across {metrics_examined} metrics examined"

    return {
        "anomalies": anomaly_items,
        "metadata": {
            "time_of_interest": time_of_interest,
            "recent_window": [recent_start_str, recent_end_str],
            "baseline_window": [baseline_start_str, baseline_end_str],
            "metrics_examined": metrics_examined,
            "host": host or "localhost",
        },
        "message": message,
        "truncated": truncated,
    }


@mcp.tool()
async def pcp_quick_investigate(
    time_of_interest: str,
    subsystem: str = "",
    lookback: str = "2hours",
    baseline_days: int = 7,
    host: str = "",
) -> dict:
    """Start here for open-ended investigation. Only requires a time of interest.

    Discovers all available metrics (or those under a subsystem prefix), runs
    anomaly detection comparing a recent window centred on the time of interest
    against a historical baseline, and returns the top anomalies ranked by
    statistical significance (z-score).

    Args:
        time_of_interest: When to investigate — ISO-8601 datetime or relative
            expression like '-2hours'. This is the centre point of the analysis window.
        subsystem: Optional metric prefix to scope investigation (e.g., 'disk',
            'network', 'kernel'). Empty = all metrics.
        lookback: Width of the comparison window centred on time_of_interest.
            Use PCP time format (e.g., '30minutes', '2hours').
        baseline_days: Number of days before the comparison window to use as
            the baseline for anomaly detection.
        host: Target host. Empty = default pmproxy host.
    """
    return await _quick_investigate_impl(
        get_client(),
        time_of_interest=time_of_interest,
        subsystem=subsystem,
        lookback=lookback,
        baseline_days=baseline_days,
        host=host,
    )
