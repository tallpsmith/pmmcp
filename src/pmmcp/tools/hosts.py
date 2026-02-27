"""pcp_get_hosts — list all monitored hosts visible to pmproxy."""

from __future__ import annotations

from pmmcp.client import PmproxyClient, PmproxyConnectionError, PmproxyError, PmproxyTimeoutError
from pmmcp.server import get_client, mcp
from pmmcp.tools._errors import _mcp_error


async def _get_hosts_impl(client: PmproxyClient, match: str, limit: int, offset: int) -> dict:
    """Core implementation, injectable for testing."""
    try:
        raw = await client.series_sources(match)
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
            "Try reducing the scope or check pmproxy performance.",
        )
    except PmproxyError as exc:
        return _mcp_error("pmproxy error", str(exc), "Check pmproxy logs for details.")

    # raw is a list of source ID strings: ["<sha1>", ...]
    source_ids: list[str] = raw

    # Fetch labels for all sources to get hostnames and other metadata
    labels_by_source: dict[str, dict] = {}
    if source_ids:
        try:
            labels_list = await client.series_labels(source_ids)
            for item in labels_list:
                labels_by_source[item["series"]] = {
                    k: str(v) for k, v in item.get("labels", {}).items()
                }
        except PmproxyError:
            pass  # Labels are optional; proceed without them

    hosts = []
    for source in source_ids:
        labels = labels_by_source.get(source, {})
        hostname = labels.get("hostname", "")
        hostnames = [hostname] if hostname else []
        hosts.append(
            {
                "source": source,
                "hostnames": hostnames,
                "labels": labels,
            }
        )

    total = len(hosts)
    page = hosts[offset : offset + limit]
    return {
        "items": page,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + limit < total,
    }


@mcp.tool()
async def pcp_get_hosts(match: str = "", limit: int = 50, offset: int = 0) -> dict:
    """List all monitored hosts visible to the pmproxy instance.

    Use this first to understand what infrastructure is available before querying metrics.

    Args:
        match: Glob pattern to filter hostnames (e.g., 'web-*')
        limit: Maximum number of hosts to return (1-1000)
        offset: Pagination offset
    """
    return await _get_hosts_impl(get_client(), match=match, limit=limit, offset=offset)
