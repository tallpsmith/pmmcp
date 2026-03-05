"""Shared timeseries window-fetching helper for tool modules."""

from __future__ import annotations

import os
from collections.abc import Iterator

from pmmcp.client import PmproxyClient, PmproxyConnectionError, PmproxyError, PmproxyTimeoutError
from pmmcp.utils import expand_time_units

_SERIES_BATCH_SIZE = int(os.getenv("PMMCP_SERIES_BATCH_SIZE", "20"))


def _chunked(lst: list, size: int) -> Iterator[list]:
    """Yield successive chunks of `size` from `lst`."""
    for i in range(0, len(lst), size):
        yield lst[i : i + size]


async def _fetch_window(
    client: PmproxyClient,
    expr: str,
    start: str,
    end: str,
    interval: str,
    limit: int,
) -> tuple[dict[tuple[str, str | None], list[float]], dict[tuple[str, str | None], list[dict]]]:
    """Fetch a time window and return (numeric_values_by_key, raw_samples_by_key).

    Raises PmproxyConnectionError, PmproxyTimeoutError, or PmproxyError on failure.
    """
    try:
        series_ids = await client.series_query(expr)
    except (PmproxyConnectionError, PmproxyTimeoutError, PmproxyError):
        raise

    if not series_ids:
        return {}, {}

    if isinstance(series_ids[0], dict):
        series_ids = list({entry["series"] for entry in series_ids})

    raw_values: list[dict] = []
    for batch in _chunked(series_ids, _SERIES_BATCH_SIZE):
        try:
            batch_values = await client.series_values(
                series=batch,
                start=expand_time_units(start),
                finish=expand_time_units(end),
                interval=interval,
                samples=limit,
            )
            raw_values.extend(batch_values)
        except (PmproxyConnectionError, PmproxyTimeoutError, PmproxyError):
            raise

    # Get metric names for series IDs
    name_by_series: dict[str, str] = {}
    try:
        labels_list: list[dict] = []
        for batch in _chunked(series_ids, _SERIES_BATCH_SIZE):
            labels_list.extend(await client.series_labels(batch))
        for item in labels_list:
            metric_name = item.get("labels", {}).get("metric.name", "")
            if metric_name:
                name_by_series[item["series"]] = metric_name
    except PmproxyError:
        pass

    # Get instance names
    instance_name_by_series: dict[str, str] = {}
    try:
        instances_list: list[dict] = []
        for batch in _chunked(series_ids, _SERIES_BATCH_SIZE):
            instances_list.extend(await client.series_instances(batch))
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
