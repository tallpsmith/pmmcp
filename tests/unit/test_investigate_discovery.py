"""Test that quick_investigate works with broad prefixes via recursive discovery.

Proves the integration between recursive namespace traversal in
_discover_metrics_impl and _quick_investigate_impl: a broad prefix
like 'kernel' (which has only non-leaf children) should still find
leaf metrics and proceed to anomaly detection, rather than returning
'No metrics found'.
"""

from __future__ import annotations

import httpx
import respx

from pmmcp.client import PmproxyClient
from pmmcp.config import PmproxyConfig
from pmmcp.tools.investigate import _quick_investigate_impl

PMPROXY_BASE = "http://localhost:44322"
TEST_CONTEXT = 1


def _mock_context():
    return httpx.Response(
        200, json={"context": TEST_CONTEXT, "hostspec": "localhost", "labels": {}}
    )


def _children_handler(request):
    """Simulate a broad prefix where 'kernel' has no direct leaf metrics.

    kernel (nonleaf: all)
      kernel.all (leaf: load)
    """
    prefix = dict(request.url.params).get("prefix", "")
    if prefix == "kernel":
        return httpx.Response(
            200,
            json={
                "context": TEST_CONTEXT,
                "name": "kernel",
                "leaf": [],
                "nonleaf": ["all"],
            },
        )
    elif prefix == "kernel.all":
        return httpx.Response(
            200,
            json={
                "context": TEST_CONTEXT,
                "name": "kernel.all",
                "leaf": ["load"],
                "nonleaf": [],
            },
        )
    return httpx.Response(404, json={"message": f"Unknown: {prefix}"})


@respx.mock
async def test_quick_investigate_finds_metrics_with_broad_prefix():
    """quick_investigate(subsystem='kernel') should NOT return 'No metrics found'.

    The old flat listing returned only non-leaf nodes for broad prefixes,
    which quick_investigate filtered out, leaving zero metrics. With
    recursive discovery, it should find kernel.all.load and proceed to
    anomaly detection.
    """
    config = PmproxyConfig(url=PMPROXY_BASE, timeout=5.0)

    respx.get(f"{PMPROXY_BASE}/pmapi/context").mock(return_value=_mock_context())
    respx.get(f"{PMPROXY_BASE}/pmapi/children").mock(side_effect=_children_handler)
    # series/query returns [] — no time series data, but that's fine;
    # we just care that discovery succeeded and anomaly detection was attempted
    respx.get(f"{PMPROXY_BASE}/series/query").mock(return_value=httpx.Response(200, json=[]))

    client = PmproxyClient(config)
    try:
        result = await _quick_investigate_impl(
            client,
            time_of_interest="-1hours",
            subsystem="kernel",
            lookback="2hours",
        )

        # The critical assertion: NOT a "No metrics found" error
        assert not result.get("isError"), (
            f"quick_investigate returned an error for broad prefix 'kernel': {result}"
        )

        # Should have actually examined kernel.all.load
        assert result["metadata"]["metrics_examined"] == 1
        assert "No anomalies detected" in result["message"]
    finally:
        await client.close()
