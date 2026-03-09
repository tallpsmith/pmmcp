"""Shared timeseries window-fetching helper for tool modules."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Iterator

from pmmcp.client import PmproxyClient, PmproxyConnectionError, PmproxyError, PmproxyTimeoutError
from pmmcp.utils import expand_time_units

_SERIES_BATCH_SIZE = int(os.getenv("PMMCP_SERIES_BATCH_SIZE", "20"))


def _chunked(lst: list, size: int) -> Iterator[list]:
    """Yield successive chunks of `size` from `lst`."""
    for i in range(0, len(lst), size):
        yield lst[i : i + size]


async def _resolve_series_ids(client: PmproxyClient, exprs: list[str]) -> list[str]:
    """Query one or more expressions and return deduplicated series IDs.

    Handles both str and dict return types from pmproxy.
    """
    seen: set[str] = set()
    result: list[str] = []

    for expr in exprs:
        try:
            raw = await client.series_query(expr)
        except (PmproxyConnectionError, PmproxyTimeoutError, PmproxyError):
            raise

        if not raw:
            continue

        for entry in raw:
            sid = entry["series"] if isinstance(entry, dict) else entry
            if sid not in seen:
                seen.add(sid)
                result.append(sid)

    return result


async def _fetch_metadata(
    client: PmproxyClient, series_ids: list[str]
) -> tuple[dict[str, str], dict[str, str]]:
    """Fetch labels and instances concurrently, returning (name_by_series, instance_name_by_series).

    Errors in either call are swallowed — the caller gets empty dicts for the failed half.
    Batching at the _fetch level via _chunked, plus transparent client-layer batching.
    """
    name_by_series: dict[str, str] = {}
    instance_name_by_series: dict[str, str] = {}

    async def fetch_labels():
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

    async def fetch_instances():
        try:
            instances_list: list[dict] = []
            for batch in _chunked(series_ids, _SERIES_BATCH_SIZE):
                instances_list.extend(await client.series_instances(batch))
            for item in instances_list:
                instance_name_by_series[item["series"]] = item.get("name", "")
        except PmproxyError:
            pass

    await asyncio.gather(fetch_labels(), fetch_instances())
    return name_by_series, instance_name_by_series


async def _fetch_descs(client: PmproxyClient, series_ids: list[str]) -> dict[str, str]:
    """Fetch metric semantics from /series/descs, returning {series_id: semantics_str}.

    Swallows PmproxyError on failure — callers fall back to treating metrics
    as instant (the safe default).
    """
    if not series_ids:
        return {}
    try:
        raw = await client.series_descs(series_ids)
        return {entry["series"]: entry.get("semantics", "instant") for entry in raw}
    except PmproxyError:
        return {}


async def _fetch_window(
    client: PmproxyClient,
    exprs: list[str],
    start: str,
    end: str,
    interval: str,
    limit: int,
    series_ids: list[str] | None = None,
) -> tuple[dict[tuple[str, str | None], list[float]], dict[tuple[str, str | None], list[dict]]]:
    """Fetch a time window and return (numeric_values_by_key, raw_samples_by_key).

    When series_ids is provided, skips the query step entirely — useful for
    dual-window deduplication where the same series are fetched twice.

    Batches large series ID lists at the _fetch level (_SERIES_BATCH_SIZE) to
    avoid overwhelming pmproxy, plus transparent client-layer batching for URL limits.

    Raises PmproxyConnectionError, PmproxyTimeoutError, or PmproxyError on failure.
    """
    if series_ids is None:
        series_ids = await _resolve_series_ids(client, exprs)

    if not series_ids:
        return {}, {}

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

    # Fetch metadata (labels + instances) concurrently
    name_by_series, instance_name_by_series = await _fetch_metadata(client, series_ids)

    # Assemble results
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
