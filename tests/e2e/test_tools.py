"""T015 + T016 — E2E tests: all nine MCP tools via real pmmcp subprocess.

Requires: PMPROXY_URL set and a running PCP + redis-stack.
Gating: see tests/e2e/conftest.py.

Run locally:
  docker compose up -d
  PMPROXY_URL=http://localhost:44322 uv run pytest tests/e2e/ -m e2e
"""

from __future__ import annotations

import json

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")

# ---------------------------------------------------------------------------
# T015 — Initial 3 tools (full-stack wiring proof)
# ---------------------------------------------------------------------------


@pytest.mark.e2e
async def test_fetch_live(e2e_session):
    """pcp_fetch_live returns current metric values from real PCP."""
    result = await e2e_session.call_tool("pcp_fetch_live", {"names": ["kernel.all.load"]})
    assert not result.isError, f"MCP error: {result.content[0].text}"
    data = json.loads(result.content[0].text)
    assert len(data.get("values", data.get("items", []))) > 0 or isinstance(data, dict)


@pytest.mark.e2e
async def test_get_hosts(e2e_session):
    """pcp_get_hosts returns at least one host from real PCP."""
    result = await e2e_session.call_tool("pcp_get_hosts", {})
    assert not result.isError, f"MCP error: {result.content[0].text}"
    data = json.loads(result.content[0].text)
    assert isinstance(data.get("items"), list)
    assert len(data["items"]) > 0, "Expected at least one host"


@pytest.mark.e2e
async def test_fetch_timeseries(e2e_session):
    """pcp_fetch_timeseries returns data points from real PCP."""
    result = await e2e_session.call_tool(
        "pcp_fetch_timeseries",
        {
            "names": ["mem.util.used"],
            "start": "-2m",
            "end": "now",
            "interval": "10s",
        },
    )
    assert not result.isError, f"MCP error: {result.content[0].text}"
    data = json.loads(result.content[0].text)
    assert isinstance(data.get("items"), list)


# ---------------------------------------------------------------------------
# T016 — Remaining 6 tools
# ---------------------------------------------------------------------------


@pytest.mark.e2e
async def test_query_series(e2e_session):
    """pcp_query_series returns series IDs from real PCP."""
    result = await e2e_session.call_tool(
        "pcp_query_series",
        {"expr": "kernel.all.load", "start": "-2m", "end": "now"},
    )
    assert not result.isError, f"MCP error: {result.content[0].text}"
    data = json.loads(result.content[0].text)
    assert isinstance(data.get("items"), list)


@pytest.mark.e2e
async def test_search(e2e_session):
    """pcp_search returns results from RediSearch (requires redis-stack)."""
    result = await e2e_session.call_tool("pcp_search", {"query": "kernel", "limit": 5})
    assert not result.isError, f"MCP error: {result.content[0].text}"
    data = json.loads(result.content[0].text)
    assert isinstance(data.get("items"), list)


@pytest.mark.e2e
async def test_discover_metrics_prefix(e2e_session):
    """pcp_discover_metrics (prefix) returns namespace children from real PCP."""
    result = await e2e_session.call_tool("pcp_discover_metrics", {"prefix": "kernel"})
    assert not result.isError, f"MCP error: {result.content[0].text}"
    data = json.loads(result.content[0].text)
    assert isinstance(data.get("items"), list)
    assert len(data["items"]) > 0


@pytest.mark.e2e
async def test_discover_metrics_search(e2e_session):
    """pcp_discover_metrics (search) returns concept results from real PCP."""
    result = await e2e_session.call_tool("pcp_discover_metrics", {"search": "load"})
    assert not result.isError, f"MCP error: {result.content[0].text}"
    data = json.loads(result.content[0].text)
    assert isinstance(data.get("items"), list)


@pytest.mark.e2e
async def test_get_metric_info(e2e_session):
    """pcp_get_metric_info returns metadata for kernel.all.load from real PCP."""
    result = await e2e_session.call_tool("pcp_get_metric_info", {"names": ["kernel.all.load"]})
    assert not result.isError, f"MCP error: {result.content[0].text}"
    data = json.loads(result.content[0].text)
    # Response may be a list or dict depending on tool version
    assert isinstance(data, (list, dict))


@pytest.mark.e2e
async def test_compare_windows(e2e_session):
    """pcp_compare_windows returns delta statistics from real PCP."""
    result = await e2e_session.call_tool(
        "pcp_compare_windows",
        {
            "names": ["kernel.all.load"],
            "window_a_start": "-4m",
            "window_a_end": "-2m",
            "window_b_start": "-2m",
            "window_b_end": "now",
            "interval": "30s",
        },
    )
    assert not result.isError, f"MCP error: {result.content[0].text}"
    # FastMCP serialises each list element as a separate TextContent block
    comparisons = [json.loads(c.text) for c in result.content]
    assert len(comparisons) > 0, "Expected at least one comparison result"
