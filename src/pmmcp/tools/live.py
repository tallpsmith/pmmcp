"""pcp_fetch_live — fetch current real-time metric values."""

from __future__ import annotations

import logging

from pmmcp.client import (
    PmproxyClient,
    PmproxyConnectionError,
    PmproxyError,
    PmproxyNotFoundError,
    PmproxyTimeoutError,
)
from pmmcp.server import get_client, mcp
from pmmcp.tools._errors import _mcp_error

logger = logging.getLogger(__name__)


async def _fetch_live_impl(
    client: PmproxyClient,
    names: list[str],
    host: str,
    instances: list[str],
) -> dict:
    """Core implementation, injectable for testing."""
    try:
        fetch_result = await client.pmapi_fetch(names, host)
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
            "Try fewer metrics or a smaller request.",
        )
    except PmproxyNotFoundError as exc:
        return _mcp_error(
            "Not found",
            f"One or more metrics not found: {exc}",
            "Use pcp_discover_metrics or pcp_search to find valid metric names.",
        )
    except PmproxyError as exc:
        return _mcp_error("pmproxy error", str(exc), "Check pmproxy logs for details.")

    timestamp = fetch_result.get("timestamp", 0)
    raw_values = fetch_result.get("values", [])

    # Build instance name lookup: fetch indom for metrics that have instances
    # We need to resolve numeric instance IDs to human-readable names.
    indom_cache: dict[str, dict[int, str]] = {}

    async def _get_instance_names(metric_name: str) -> dict[int, str]:
        if metric_name in indom_cache:
            return indom_cache[metric_name]
        try:
            indom_data = await client.pmapi_indom(metric_name, host)
            mapping = {
                inst["instance"]: inst["name"]
                for inst in indom_data.get("instances", [])
                if inst.get("instance") is not None
            }
        except PmproxyError:
            mapping = {}
        indom_cache[metric_name] = mapping
        return mapping

    values_out = []
    for metric_entry in raw_values:
        metric_name = metric_entry.get("name", "")
        raw_instances = metric_entry.get("instances", [])

        # Get instance name mapping
        has_instances = any(inst.get("instance") is not None for inst in raw_instances)
        inst_names: dict[int, str] = {}
        if has_instances:
            inst_names = await _get_instance_names(metric_name)

        resolved_instances = []
        for inst in raw_instances:
            inst_id = inst.get("instance")
            inst_name = inst_names.get(inst_id, str(inst_id)) if inst_id is not None else None
            value = inst.get("value")

            # Apply instance filter
            if instances and inst_name and inst_name not in instances:
                continue

            resolved_instances.append(
                {
                    "instance": inst_name,
                    "value": value,
                }
            )

        values_out.append({"name": metric_name, "instances": resolved_instances})

    return {
        "timestamp": timestamp,
        "values": values_out,
    }


@mcp.tool()
async def pcp_fetch_live(
    names: list[str],
    host: str = "",
    instances: list[str] = [],  # noqa: B006
) -> dict:
    """Fetch current (real-time) values for one or more metrics from a live host.

    Returns the most recent sample for each metric and instance.

    Args:
        names: List of metric names to fetch
        host: Target hostname (empty uses default pmproxy host)
        instances: Filter to specific instances (empty means all)
    """
    return await _fetch_live_impl(get_client(), names=names, host=host, instances=instances)
