"""pcp_discover_metrics and pcp_get_metric_info — metric namespace browsing and metadata."""

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


async def _discover_metrics_impl(
    client: PmproxyClient,
    host: str,
    prefix: str,
    search: str,
    limit: int,
    offset: int,
) -> dict:
    """Core implementation, injectable for testing."""
    if prefix and search:
        return _mcp_error(
            "Invalid parameters",
            "The 'prefix' and 'search' parameters are mutually exclusive.",
            "Provide either 'prefix' for tree browsing or 'search' for full-text search, not both.",
        )

    if search:
        # Use search endpoint
        try:
            raw = await client.search_text(search, limit=limit, offset=offset)
        except PmproxyConnectionError as exc:
            return _mcp_error("Connection error", str(exc), "Check pmproxy connectivity.")
        except PmproxyTimeoutError as exc:
            return _mcp_error("Timeout", str(exc), "Try a shorter or more specific query.")
        except PmproxyError as exc:
            return _mcp_error(
                "pmproxy error", str(exc), "Ensure pmproxy has RediSearch configured."
            )

        total = raw.get("total", 0)
        items = [
            {"name": r["name"], "oneline": r.get("oneline", ""), "leaf": True}
            for r in raw.get("results", [])
        ]
        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total,
        }

    # Use namespace tree (pmapi/children) with recursive leaf traversal
    MAX_DEPTH = 10

    async def _collect_leaves(node_prefix: str, depth: int, remaining: int) -> list[dict]:
        """Recursively walk namespace tree, collecting only leaf metrics.

        Args:
            node_prefix: Current namespace node to expand.
            depth: Current recursion depth (capped at MAX_DEPTH).
            remaining: Max leaves still needed. Stops early once reached.
        """
        if depth > MAX_DEPTH or remaining <= 0:
            return []

        raw = await client.pmapi_children(node_prefix, host)
        base = raw.get("name", node_prefix)
        leaf_names = raw.get("leaf", [])
        nonleaf_names = raw.get("nonleaf", [])

        leaves: list[dict] = []
        for name in leaf_names:
            full_name = f"{base}.{name}" if base else name
            leaves.append({"name": full_name, "oneline": "", "leaf": True})
            if len(leaves) >= remaining:
                return leaves

        for name in nonleaf_names:
            if len(leaves) >= remaining:
                break
            full_name = f"{base}.{name}" if base else name
            try:
                sub_leaves = await _collect_leaves(full_name, depth + 1, remaining - len(leaves))
                leaves.extend(sub_leaves)
            except (PmproxyNotFoundError, PmproxyError):
                logger.debug("Skipping inaccessible subtree: %s", full_name)

        return leaves

    try:
        all_leaves = await _collect_leaves(prefix, 0, limit + offset)
    except PmproxyConnectionError as exc:
        return _mcp_error("Connection error", str(exc), "Check pmproxy connectivity.")
    except PmproxyTimeoutError as exc:
        return _mcp_error("Timeout", str(exc), "Try a more specific prefix.")
    except PmproxyNotFoundError as exc:
        return _mcp_error(
            "Not found",
            f"Namespace prefix not found: {exc}",
            "Use pcp_search to find valid metric namespace prefixes.",
        )
    except PmproxyError as exc:
        return _mcp_error("pmproxy error", str(exc), "Check pmproxy logs.")

    collected = len(all_leaves)
    cap = limit + offset
    # If we hit the collection cap, more leaves likely exist beyond what we gathered
    truncated = collected >= cap
    page = all_leaves[offset : offset + limit]
    return {
        "items": page,
        "total": collected,
        "limit": limit,
        "offset": offset,
        "has_more": truncated or offset + limit < collected,
    }


async def _get_metric_info_impl(
    client: PmproxyClient,
    names: list[str],
    host: str,
) -> dict | list:
    """Core implementation, injectable for testing."""
    try:
        raw = await client.pmapi_metric(names, host)
    except PmproxyConnectionError as exc:
        return _mcp_error("Connection error", str(exc), "Check pmproxy connectivity.")
    except PmproxyTimeoutError as exc:
        return _mcp_error("Timeout", str(exc), "Try fewer metric names.")
    except PmproxyNotFoundError as exc:
        return _mcp_error(
            "Not found",
            f"One or more metrics not found: {exc}",
            "Use pcp_discover_metrics or pcp_search to find valid metric names.",
        )
    except PmproxyError as exc:
        return _mcp_error("pmproxy error", str(exc), "Check pmproxy logs.")

    metrics_raw = raw.get("metrics", [])
    metrics_out = []

    for m in metrics_raw:
        metric_name = m.get("name", "")
        indom_raw = m.get("indom")
        indom = None if indom_raw is None or str(indom_raw).lower() == "none" else indom_raw

        metric = {
            "name": metric_name,
            "pmid": m.get("pmid", ""),
            "type": (m.get("type") or "").lower(),
            "semantics": m.get("sem", ""),
            "units": m.get("units", ""),
            "indom": indom,
            "series": m.get("series", ""),
            "source": m.get("source", ""),
            "labels": {k: str(v) for k, v in m.get("labels", {}).items()},
            "oneline": m.get("text-oneline", ""),
            "helptext": m.get("text-help", ""),
        }

        # Fetch indom instances if metric has an instance domain
        if indom:
            try:
                indom_data = await client.pmapi_indom(metric_name, host)
                metric["instances"] = [
                    {"instance": inst["instance"], "name": inst["name"]}
                    for inst in indom_data.get("instances", [])
                ]
            except PmproxyError:
                metric["instances"] = []

        metrics_out.append(metric)

    return metrics_out


@mcp.tool()
async def pcp_discover_metrics(
    host: str = "",
    prefix: str = "",
    search: str = "",
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Browse the metric namespace tree or search for metrics by keyword.

    Returns metric names with one-line descriptions. Use this to find which metrics
    exist before fetching their values. Supply either prefix for tree browsing or
    search for full-text search — not both.

    Args:
        host: Target hostname (empty uses default pmproxy host)
        prefix: Metric namespace prefix to browse children of (e.g., 'kernel.percpu').
            Mutually exclusive with 'search'.
        search: Full-text search query across metric names and descriptions.
            Mutually exclusive with 'prefix'.
        limit: Maximum number of metrics to return (1-1000).
            For exploration use 50; increase to 200+ for analysis.
        offset: Pagination offset
    """
    return await _discover_metrics_impl(
        get_client(), host=host, prefix=prefix, search=search, limit=limit, offset=offset
    )


@mcp.tool()
async def pcp_get_metric_info(names: list[str], host: str = "") -> dict | list:
    """Get detailed metadata for one or more specific metrics.

    Returns full help text, type, units, semantics, instance domain members, and labels.
    Use this to understand what a metric measures before interpreting its values.

    Args:
        names: List of fully-qualified metric names
            (e.g., ['kernel.percpu.cpu.user', 'mem.util.free'])
        host: Target hostname (empty uses default pmproxy host)
    """
    return await _get_metric_info_impl(get_client(), names=names, host=host)
