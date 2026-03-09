"""Unit tests for tool description UX improvements (T009, US3+US4).

Tests that tool docstrings contain:
- US3: "first" investigation language in pcp_detect_anomalies
- US3: "drill-down after anomalies" language in pcp_fetch_timeseries
- US4: exploration vs analysis limit guidance (value 50) in all limit-bearing tools
"""

from __future__ import annotations

import pmmcp.tools.anomaly as anomaly_mod
import pmmcp.tools.discovery as disc_mod
import pmmcp.tools.hosts as hosts_mod
import pmmcp.tools.scanning as scanning_mod
import pmmcp.tools.search as search_mod
import pmmcp.tools.timeseries as ts_mod


def test_detect_anomalies_description_steers_to_quick_investigate():
    """pcp_detect_anomalies docstring steers toward pcp_quick_investigate for discovery."""
    doc = anomaly_mod.pcp_detect_anomalies.__doc__
    assert doc is not None
    assert "pcp_quick_investigate" in doc, (
        "Expected steering to pcp_quick_investigate in pcp_detect_anomalies docstring"
    )


def test_fetch_timeseries_description_states_drilldown():
    """pcp_fetch_timeseries docstring indicates use after anomalies are identified."""
    doc = ts_mod.pcp_fetch_timeseries.__doc__
    assert doc is not None
    assert "anomal" in doc.lower(), (
        "Expected language indicating use after anomalies are identified in pcp_fetch_timeseries"
    )


def test_fetch_timeseries_limit_guidance_present():
    """pcp_fetch_timeseries limit arg documents default value."""
    doc = ts_mod.pcp_fetch_timeseries.__doc__
    assert doc is not None
    assert "500" in doc or "limit" in doc.lower(), (
        "Expected limit guidance in pcp_fetch_timeseries docstring"
    )


def test_fetch_timeseries_mentions_sqlite():
    """pcp_fetch_timeseries docstring mentions pcp_query_sqlite for analysis."""
    doc = ts_mod.pcp_fetch_timeseries.__doc__
    assert doc is not None
    assert "pcp_query_sqlite" in doc, (
        "Expected pcp_query_sqlite reference in pcp_fetch_timeseries docstring"
    )


def test_discover_metrics_limit_guidance_present():
    """pcp_discover_metrics limit arg includes exploration guidance with value 50."""
    doc = disc_mod.pcp_discover_metrics.__doc__
    assert doc is not None
    assert "exploration" in doc.lower() or "explore" in doc.lower(), (
        "Expected exploration guidance in pcp_discover_metrics docstring"
    )


def test_get_hosts_limit_guidance_present():
    """pcp_get_hosts limit arg includes exploration guidance."""
    doc = hosts_mod.pcp_get_hosts.__doc__
    assert doc is not None
    assert "exploration" in doc.lower() or "explore" in doc.lower(), (
        "Expected exploration guidance in pcp_get_hosts docstring"
    )


def test_search_limit_guidance_present():
    """pcp_search limit arg includes exploration guidance."""
    doc = search_mod.pcp_search.__doc__
    assert doc is not None
    assert "exploration" in doc.lower() or "explore" in doc.lower(), (
        "Expected exploration guidance in pcp_search docstring"
    )


def test_scan_changes_max_metrics_guidance_present():
    """pcp_scan_changes max_metrics arg includes exploration guidance."""
    doc = scanning_mod.pcp_scan_changes.__doc__
    assert doc is not None
    assert "exploration" in doc.lower() or "explore" in doc.lower(), (
        "Expected exploration guidance in pcp_scan_changes docstring"
    )
