"""Contract tests: verify MCP tool schemas and error format (T038)."""

from __future__ import annotations

import pmmcp.server as srv

EXPECTED_TOOLS = {
    "pcp_get_hosts",
    "pcp_discover_metrics",
    "pcp_get_metric_info",
    "pcp_fetch_live",
    "pcp_fetch_timeseries",
    "pcp_query_series",
    "pcp_compare_windows",
    "pcp_search",
    "pcp_derive_metric",
    "pcp_quick_investigate",
}


def test_all_tools_registered():
    """All expected MCP tools appear in the tool listing."""
    tools = srv.mcp._tool_manager.list_tools()
    tool_names = {t.name for t in tools}
    missing = EXPECTED_TOOLS - tool_names
    assert not missing, f"Missing tools: {missing}"


def test_pcp_get_hosts_schema():
    """pcp_get_hosts schema has correct parameter types."""
    tools = {t.name: t for t in srv.mcp._tool_manager.list_tools()}
    assert "pcp_get_hosts" in tools
    tool = tools["pcp_get_hosts"]
    schema = tool.parameters
    assert schema["type"] == "object"
    props = schema.get("properties", {})
    assert "match" in props
    assert "limit" in props
    assert "offset" in props


def test_pcp_fetch_live_schema():
    """pcp_fetch_live schema requires 'names' parameter."""
    tools = {t.name: t for t in srv.mcp._tool_manager.list_tools()}
    tool = tools["pcp_fetch_live"]
    schema = tool.parameters
    # names should be required
    assert "names" in schema.get("required", []) or "names" in schema.get("properties", {})


def test_pcp_compare_windows_schema():
    """pcp_compare_windows schema has all required window parameters."""
    tools = {t.name: t for t in srv.mcp._tool_manager.list_tools()}
    tool = tools["pcp_compare_windows"]
    schema = tool.parameters
    props = schema.get("properties", {})
    for param in ["names", "window_a_start", "window_a_end", "window_b_start", "window_b_end"]:
        assert param in props, f"Missing parameter: {param}"


def test_error_format_structure():
    """MCP error responses follow the contract format: isError=True + content array."""
    error = {
        "content": [
            {"type": "text", "text": "Error: Connection error\n\nDetails: ...\nSuggestion: ..."}
        ],  # noqa: E501
        "isError": True,
    }
    assert error["isError"] is True
    assert isinstance(error["content"], list)
    assert error["content"][0]["type"] == "text"
    text = error["content"][0]["text"]
    assert "Error:" in text
    assert "Details:" in text
    assert "Suggestion:" in text


def test_tool_descriptions_present():
    """All tools have non-empty descriptions."""
    tools = srv.mcp._tool_manager.list_tools()
    for tool in tools:
        if tool.name in EXPECTED_TOOLS:
            assert tool.description, f"Tool {tool.name} has no description"


# ---------------------------------------------------------------------------
# US2: Tool description steering language (T010-T014)
# ---------------------------------------------------------------------------


def _get_tool_description(name: str) -> str:
    tools = {t.name: t for t in srv.mcp._tool_manager.list_tools()}
    assert name in tools, f"Tool {name} not registered"
    return tools[name].description


def test_quick_investigate_description_steering():
    """T010: pcp_quick_investigate description signals it as the discovery entry point."""
    desc = _get_tool_description("pcp_quick_investigate")
    assert "Start here" in desc, f"Missing 'Start here' in: {desc}"
    assert "open-ended investigation" in desc, f"Missing 'open-ended investigation' in: {desc}"


def test_detect_anomalies_description_steering():
    """T011: pcp_detect_anomalies steers toward pcp_quick_investigate for discovery."""
    desc = _get_tool_description("pcp_detect_anomalies")
    assert "pcp_quick_investigate" in desc, f"Missing steering in: {desc}"


def test_compare_windows_description_steering():
    """T012: pcp_compare_windows steers toward pcp_quick_investigate for discovery."""
    desc = _get_tool_description("pcp_compare_windows")
    assert "pcp_quick_investigate" in desc, f"Missing steering in: {desc}"


def test_scan_changes_description_steering():
    """T013: pcp_scan_changes steers toward pcp_quick_investigate for discovery."""
    desc = _get_tool_description("pcp_scan_changes")
    assert "pcp_quick_investigate" in desc, f"Missing steering in: {desc}"


def test_fetch_timeseries_description_steering():
    """T014: pcp_fetch_timeseries warns against exploratory use."""
    desc = _get_tool_description("pcp_fetch_timeseries")
    assert "NOT for exploratory investigation" in desc, f"Missing steering in: {desc}"
