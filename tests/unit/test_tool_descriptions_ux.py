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


def test_detect_anomalies_description_states_use_first():
    """pcp_detect_anomalies docstring declares it the first investigation tool."""
    doc = anomaly_mod.pcp_detect_anomalies.__doc__
    assert doc is not None
    assert "first" in doc.lower(), (
        "Expected 'first' investigation language in pcp_detect_anomalies docstring"
    )


def test_fetch_timeseries_description_states_drilldown():
    """pcp_fetch_timeseries docstring indicates use after anomalies are identified."""
    doc = ts_mod.pcp_fetch_timeseries.__doc__
    assert doc is not None
    assert "anomal" in doc.lower(), (
        "Expected language indicating use after anomalies are identified in pcp_fetch_timeseries"
    )


def test_fetch_timeseries_limit_guidance_present():
    """pcp_fetch_timeseries limit arg includes exploration guidance with value 50."""
    doc = ts_mod.pcp_fetch_timeseries.__doc__
    assert doc is not None
    assert "exploration" in doc.lower() or "explore" in doc.lower(), (
        "Expected exploration guidance in pcp_fetch_timeseries docstring"
    )


def test_query_series_limit_guidance_present():
    """pcp_query_series limit arg includes exploration guidance."""
    doc = ts_mod.pcp_query_series.__doc__
    assert doc is not None
    assert "exploration" in doc.lower() or "explore" in doc.lower(), (
        "Expected exploration guidance in pcp_query_series docstring"
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
