"""pcp_fetch_timeseries and pcp_query_series — historical time-series data."""

from __future__ import annotations

import logging

from pmmcp.client import PmproxyClient, PmproxyConnectionError, PmproxyError, PmproxyTimeoutError
from pmmcp.server import get_client, mcp
from pmmcp.utils import resolve_interval

logger = logging.getLogger(__name__)


def _mcp_error(category: str, description: str, suggestion: str) -> dict:
    text = f"Error: {category}\n\nDetails: {description}\nSuggestion: {suggestion}"
    return {"content": [{"type": "text", "text": text}], "isError": True}


async def _resolve_series_and_fetch(
    client: PmproxyClient,
    expr: str,
    start: str,
    end: str,
    interval: str,
    limit: int,
    offset: int,
) -> dict:
    """Query series IDs by expression, then fetch values. Returns raw grouped data."""
    resolved = resolve_interval(start, end, interval)

    try:
        series_ids = await client.series_query(expr)
    except PmproxyConnectionError as exc:
        return _mcp_error(
            "Connection error",
            f"pmproxy is unreachable: {exc}",
            "Check that pmproxy is running and the URL is correct.",
        )
    except PmproxyTimeoutError as exc:
        return _mcp_error(
            "Timeout",
            f"pmproxy did not respond in time: {exc}",
            "Try reducing the time window or number of metrics.",
        )
    except PmproxyError as exc:
        return _mcp_error("pmproxy error", str(exc), "Check the metric name or expression.")

    if not series_ids:
        return {"items": [], "total": 0, "limit": limit, "offset": offset, "has_more": False}

    # Ensure series_ids are strings (not value-with-timestamp objects)
    if isinstance(series_ids[0], dict):
        series_ids = list({entry["series"] for entry in series_ids})

    try:
        values = await client.series_values(
            series=series_ids,
            start=start,
            finish=end,
            interval=resolved,
            samples=limit,
        )
    except PmproxyTimeoutError as exc:
        return _mcp_error(
            "Timeout",
            f"pmproxy did not respond in time: {exc}",
            "Try reducing the time window, interval, or limit.",
        )
    except PmproxyError as exc:
        return _mcp_error("pmproxy error", str(exc), "Check pmproxy logs for details.")

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

    # Get instance names if needed
    instance_name_by_series: dict[str, str] = {}
    try:
        instances_list = await client.series_instances(series_ids)
        for item in instances_list:
            instance_name_by_series[item["series"]] = item.get("name", "")
    except PmproxyError:
        pass

    # Group data points by (metric_name, instance)
    grouped: dict[tuple[str, str | None], list[dict]] = {}
    for point in values:
        series_id = point["series"]
        metric_name = name_by_series.get(series_id, series_id)
        instance_name = instance_name_by_series.get(series_id) or None
        key = (metric_name, instance_name)
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(
            {
                "timestamp": point["timestamp"],
                "value": point["value"],
            }
        )

    all_items = [
        {
            "name": name,
            "instance": inst,
            "samples": samples,
        }
        for (name, inst), samples in grouped.items()
    ]

    total = len(all_items)
    page = all_items[offset : offset + limit] if limit < total else all_items
    return {
        "items": page,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + limit < total,
    }


async def _fetch_timeseries_impl(
    client: PmproxyClient,
    names: list[str],
    start: str,
    end: str,
    interval: str,
    host: str,
    instances: list[str],
    limit: int,
    offset: int,
    zone: str,
) -> dict:
    """Core implementation for pcp_fetch_timeseries."""
    # Query each metric individually (pmproxy /series/query doesn't support
    # multi-metric 'or' expressions reliably) and union the series IDs.
    all_items: list[dict] = []
    last_error: dict | None = None

    for name in names:
        expr = f'{name}{{hostname=="{host}"}}' if host else name
        result = await _resolve_series_and_fetch(
            client,
            expr=expr,
            start=start,
            end=end,
            interval=interval,
            limit=limit,
            offset=0,
        )
        if result.get("isError"):
            last_error = result
            continue
        all_items.extend(result.get("items", []))

    if not all_items and last_error:
        return last_error

    total = len(all_items)
    page = all_items[offset : offset + limit]
    return {
        "items": page,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + limit < total,
    }


async def _query_series_impl(
    client: PmproxyClient,
    expr: str,
    start: str,
    end: str,
    interval: str,
    limit: int,
    offset: int,
) -> dict:
    """Core implementation for pcp_query_series."""
    return await _resolve_series_and_fetch(
        client,
        expr=expr,
        start=start,
        end=end,
        interval=interval,
        limit=limit,
        offset=offset,
    )


@mcp.tool()
async def pcp_fetch_timeseries(
    names: list[str],
    start: str = "-1hour",
    end: str = "now",
    interval: str = "auto",
    host: str = "",
    instances: list[str] = [],  # noqa: B006
    limit: int = 500,
    offset: int = 0,
    zone: str = "UTC",
) -> dict:
    """Fetch historical time-series values for one or more metrics over a time window.

    Supports the hierarchical sampling strategy: start with wide windows and coarse
    intervals, then drill down to interesting periods at finer granularity.
    The 'auto' interval selects granularity based on window size.

    Auto-interval mapping: <=1h->15s, <=24h->5min, <=7d->1hour, >7d->6hour

    Args:
        names: List of metric names
        start: Start time (ISO-8601 or PCP relative e.g. '-6hours', '-7days')
        end: End time (ISO-8601 or 'now')
        interval: Sampling interval (e.g., '15s', '5min', '1hour') or 'auto'
        host: Target hostname or glob (empty queries all hosts)
        instances: Filter to specific instances (empty means all)
        limit: Maximum data points per metric/instance (default 500)
        offset: Pagination offset
        zone: Timezone for timestamps
    """
    return await _fetch_timeseries_impl(
        get_client(),
        names=names,
        start=start,
        end=end,
        interval=interval,
        host=host,
        instances=instances,
        limit=limit,
        offset=offset,
        zone=zone,
    )


@mcp.tool()
async def pcp_query_series(
    expr: str,
    start: str = "-1hour",
    end: str = "now",
    interval: str = "auto",
    limit: int = 500,
    offset: int = 0,
) -> dict:
    """Execute a raw PCP series query expression for advanced filtering.

    The query language supports label matching, arithmetic, and aggregation.
    Use when precise control is needed (e.g., 'kernel.percpu.cpu.user{hostname=="web-01"}').

    Args:
        expr: PCP series query expression
        start: Start time
        end: End time
        interval: Sampling interval or 'auto'
        limit: Max data points per series
        offset: Pagination offset
    """
    return await _query_series_impl(
        get_client(),
        expr=expr,
        start=start,
        end=end,
        interval=interval,
        limit=limit,
        offset=offset,
    )
