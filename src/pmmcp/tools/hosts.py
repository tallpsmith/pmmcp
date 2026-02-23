"""pcp_get_hosts — list all monitored hosts visible to pmproxy."""

from __future__ import annotations

from pmmcp.client import PmproxyClient, PmproxyConnectionError, PmproxyError, PmproxyTimeoutError
from pmmcp.server import get_client, mcp


def _mcp_error(category: str, description: str, suggestion: str) -> dict:
    text = f"Error: {category}\n\nDetails: {description}\nSuggestion: {suggestion}"
    return {"content": [{"type": "text", "text": text}], "isError": True}


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

    # Fetch labels for all sources to populate Host.labels
    labels_by_source: dict[str, dict] = {}
    if raw:
        source_ids = [entry["source"] for entry in raw]
        try:
            labels_list = await client.series_labels(source_ids)
            for item in labels_list:
                labels_by_source[item["series"]] = {
                    k: str(v) for k, v in item.get("labels", {}).items()
                }
        except PmproxyError:
            pass  # Labels are optional; proceed without them

    hosts = []
    for entry in raw:
        source = entry["source"]
        hostnames = [c for c in entry.get("context", []) if not c.startswith("/")]
        hosts.append(
            {
                "source": source,
                "hostnames": hostnames,
                "labels": labels_by_source.get(source, {}),
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
