"""pcp_derive_metric — create derived (computed) metrics on-the-fly."""

from __future__ import annotations

from pmmcp.client import PmproxyClient, PmproxyConnectionError, PmproxyError, PmproxyTimeoutError
from pmmcp.server import get_client, mcp


def _mcp_error(category: str, description: str, suggestion: str) -> dict:
    text = f"Error: {category}\n\nDetails: {description}\nSuggestion: {suggestion}"
    return {"content": [{"type": "text", "text": text}], "isError": True}


async def _derive_metric_impl(
    client: PmproxyClient,
    name: str,
    expr: str,
    host: str,
) -> dict:
    """Core implementation, injectable for testing."""
    try:
        raw = await client.pmapi_derive(name, expr, host)
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
            "Retry with a simpler expression.",
        )
    except PmproxyError as exc:
        return _mcp_error(
            "pmproxy error",
            f"Failed to derive metric '{name}': {exc}",
            "Check the expression syntax and that all referenced metrics exist.",
        )

    if not raw.get("success", False):
        pmproxy_msg = raw.get("message", "Unknown error from pmproxy")
        return _mcp_error(
            "pmproxy error",
            f"Failed to derive metric '{name}': {pmproxy_msg}",
            "Check the expression syntax and that all referenced metrics exist.",
        )

    return {
        "success": True,
        "name": name,
        "message": f"Derived metric '{name}' created successfully.",
    }


@mcp.tool()
async def pcp_derive_metric(name: str, expr: str, host: str = "") -> dict:
    """Create a derived (computed) metric on-the-fly using PCP's derived metric expression syntax.

    Allows defining custom ratios, rates, or aggregations. Derived metrics can then
    be fetched like any other metric using pcp_fetch_live or pcp_fetch_timeseries.

    Args:
        name: Name for the derived metric (e.g., 'derived.cpu.total_util')
        expr: PCP derived metric expression
            (e.g., '100 * (kernel.all.cpu.user + kernel.all.cpu.sys) / hinv.ncpu')
        host: Target hostname for the context
    """
    return await _derive_metric_impl(get_client(), name=name, expr=expr, host=host)
