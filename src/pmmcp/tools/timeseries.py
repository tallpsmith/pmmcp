"""pcp_fetch_timeseries — historical time-series data, stored in session SQLite DB."""

from __future__ import annotations

import logging

from pmmcp.client import PmproxyClient, PmproxyConnectionError, PmproxyError, PmproxyTimeoutError
from pmmcp.server import get_client, get_session_db, mcp
from pmmcp.session_db import SessionDB
from pmmcp.tools._errors import _mcp_error
from pmmcp.tools._fetch import _fetch_window
from pmmcp.utils import natural_samples as compute_natural_samples
from pmmcp.utils import resolve_interval

logger = logging.getLogger(__name__)


async def _fetch_timeseries_impl(
    client: PmproxyClient,
    session_db: SessionDB,
    names: list[str],
    start: str,
    end: str,
    interval: str,
    host: str,
    instances: list[str],
    limit: int,
    offset: int,
    expr: str,
) -> dict:
    """Fetch timeseries data and write to session SQLite DB.

    Returns compact metadata — use pcp_query_sqlite to analyse the data.
    """
    resolved = resolve_interval(start, end, interval)
    try:
        effective_samples = min(limit, compute_natural_samples(start, end, resolved))
    except ValueError:
        effective_samples = limit

    # Build expression list: either from explicit expr or from metric names
    if expr:
        exprs = [expr]
    else:
        exprs = [f'{name}{{hostname=="{host}"}}' if host else name for name in names]

    all_rows: list[dict] = []
    metrics_seen: set[str] = set()
    last_error: dict | None = None

    for expression in exprs:
        try:
            _, raw_samples = await _fetch_window(
                client,
                exprs=[expression],
                start=start,
                end=end,
                interval=resolved,
                limit=effective_samples,
            )
        except PmproxyConnectionError as exc:
            last_error = _mcp_error(
                "Connection error",
                f"pmproxy is unreachable: {exc}",
                "Check that pmproxy is running and the URL is correct.",
            )
            continue
        except PmproxyTimeoutError as exc:
            last_error = _mcp_error(
                "Timeout",
                f"pmproxy did not respond in time: {exc}",
                "Try reducing the time window or number of metrics.",
            )
            continue
        except PmproxyError as exc:
            last_error = _mcp_error(
                "pmproxy error",
                str(exc),
                "Check the metric name or expression.",
            )
            continue

        logger.info(
            "fetch_window returned %d keys for expr=%r",
            len(raw_samples),
            expression,
        )
        for (metric_name, instance), samples in raw_samples.items():
            logger.info("  key=(%r, %r) -> %d samples", metric_name, instance, len(samples))
            metrics_seen.add(metric_name)
            for sample in samples:
                all_rows.append(
                    {
                        "metric": metric_name,
                        "instance": instance,
                        "host": host or None,
                        "timestamp": sample["timestamp"],
                        "value": sample["value"],
                    }
                )

    if not all_rows and last_error:
        return last_error

    if all_rows:
        await session_db.insert_timeseries(all_rows)

    return {
        "row_count": len(all_rows),
        "metrics": sorted(metrics_seen),
        "window": {"start": start, "end": end, "interval": resolved},
        "hint": "Use pcp_query_sqlite to analyse this data",
    }


@mcp.tool()
async def pcp_fetch_timeseries(
    names: list[str] = [],  # noqa: B006
    start: str = "-1hour",
    end: str = "now",
    interval: str = "auto",
    host: str = "",
    instances: list[str] = [],  # noqa: B006
    limit: int = 500,
    offset: int = 0,
    expr: str = "",
) -> dict:
    """Fetch historical time-series data into the session database for SQL analysis.

    Data is stored in the session SQLite DB — use pcp_query_sqlite to analyse it.
    Multiple calls accumulate data: fetch different metrics or time windows, then
    JOIN/compare them with SQL.

    NOT for exploratory investigation — use pcp_quick_investigate for discovery.
    Use for targeted drill-down after anomalies are identified.

    The session DB schema: timeseries(metric TEXT, instance TEXT, host TEXT,
    timestamp REAL, value REAL).

    Auto-interval mapping: <=1h->15s, <=24h->5min, <=7d->1hour, >7d->6hour

    Args:
        names: List of metric names (ignored if expr is provided)
        start: Start time (ISO-8601 or PCP relative e.g. '-6hours', '-7days')
        end: End time (ISO-8601 or 'now')
        interval: Sampling interval (e.g., '15s', '5min', '1hour') or 'auto'
        host: Target hostname or glob (empty queries all hosts)
        instances: Filter to specific instances (empty means all)
        limit: Maximum data points per metric/instance (default 500)
        offset: Pagination offset
        expr: Raw PCP series expression (overrides names if provided)
    """
    return await _fetch_timeseries_impl(
        get_client(),
        get_session_db(),
        names=names,
        start=start,
        end=end,
        interval=interval,
        host=host,
        instances=instances,
        limit=limit,
        offset=offset,
        expr=expr,
    )
