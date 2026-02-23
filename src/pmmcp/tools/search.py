"""pcp_search — full-text search across all metrics, instances, and indoms."""

from __future__ import annotations

from pmmcp.client import PmproxyClient, PmproxyConnectionError, PmproxyError, PmproxyTimeoutError
from pmmcp.server import get_client, mcp


def _mcp_error(category: str, description: str, suggestion: str) -> dict:
    text = f"Error: {category}\n\nDetails: {description}\nSuggestion: {suggestion}"
    return {"content": [{"type": "text", "text": text}], "isError": True}


async def _search_impl(
    client: PmproxyClient,
    query: str,
    type: str,
    limit: int,
    offset: int,
) -> dict:
    """Core implementation, injectable for testing."""
    # Map type to pmproxy result_type param
    result_type = "" if type == "all" else type

    try:
        raw = await client.search_text(query, result_type=result_type, limit=limit, offset=offset)
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
            "Try a shorter or more specific query.",
        )
    except PmproxyError as exc:
        return _mcp_error(
            "pmproxy error",
            str(exc),
            "Ensure pmproxy is configured with a Valkey/Redis + RediSearch backend.",
        )

    total = raw.get("total", 0)
    results = raw.get("results", [])
    items = [
        {
            "name": r.get("name", ""),
            "type": r.get("type", ""),
            "oneline": r.get("oneline", ""),
            "helptext": r.get("helptext", ""),
            "score": r.get("score", 0.0),
        }
        for r in results
    ]

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + limit < total,
    }


@mcp.tool()
async def pcp_search(
    query: str,
    type: str = "all",
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """Full-text search across all metric names, help text, instance domains, and labels.

    Returns ranked results. Use when you need to find metrics related to a concept
    (e.g., 'disk latency', 'network errors') without knowing exact PCP metric names.

    Args:
        query: Free-text search query
        type: Result type filter: 'all', 'metric', 'indom', or 'instance'
        limit: Maximum results (1-100)
        offset: Pagination offset
    """
    return await _search_impl(get_client(), query=query, type=type, limit=limit, offset=offset)
