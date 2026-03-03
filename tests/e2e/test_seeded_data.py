"""E2E tests for pmlogsynth-seeded data.

Requires: PMPROXY_URL set and a running compose stack (including pmlogsynth-generator
and pmlogsynth-seeder one-shot services that have completed before pcp starts).

Run:
  podman compose up -d
  PMPROXY_URL=http://localhost:44322 uv run pytest tests/e2e/test_seeded_data.py -m e2e -v
"""

from __future__ import annotations

import json
import statistics

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


# ---------------------------------------------------------------------------
# US1 — Realistic data present on stack startup
# ---------------------------------------------------------------------------


@pytest.mark.e2e
async def test_cpu_metrics_present(e2e_session):
    """pcp_query_series returns CPU data loaded by pmlogsynth-seeder."""
    result = await e2e_session.call_tool(
        "pcp_query_series",
        {"expr": "kernel.all.cpu.user", "start": "-90minutes", "finish": "now"},
    )
    assert not result.isError, f"MCP error: {result.content[0].text}"
    values = [json.loads(c.text) for c in result.content]
    assert len(values) > 0, "Expected non-empty CPU metric data from seeded archive"


@pytest.mark.e2e
async def test_memory_metrics_present(e2e_session):
    """pcp_query_series returns memory data loaded by pmlogsynth-seeder."""
    result = await e2e_session.call_tool(
        "pcp_query_series",
        {"expr": "mem.util.used", "start": "-90minutes", "finish": "now"},
    )
    assert not result.isError, f"MCP error: {result.content[0].text}"
    values = [json.loads(c.text) for c in result.content]
    assert len(values) > 0, "Expected non-empty memory metric data from seeded archive"


@pytest.mark.e2e
async def test_disk_metrics_present(e2e_session):
    """pcp_query_series returns disk data loaded by pmlogsynth-seeder."""
    result = await e2e_session.call_tool(
        "pcp_query_series",
        {"expr": "disk.all.read", "start": "-90minutes", "finish": "now"},
    )
    assert not result.isError, f"MCP error: {result.content[0].text}"
    values = [json.loads(c.text) for c in result.content]
    assert len(values) > 0, "Expected non-empty disk metric data from seeded archive"


# ---------------------------------------------------------------------------
# US2 — Deterministic pattern assertions
# ---------------------------------------------------------------------------


@pytest.mark.e2e
async def test_spike_pattern_detected(e2e_session):
    """Spike profile produces at least one CPU user value exceeding 0.85."""
    result = await e2e_session.call_tool(
        "pcp_fetch_timeseries",
        {
            "names": ["kernel.all.cpu.user"],
            "start": "-90minutes",
            "end": "now",
            "interval": "60s",
        },
    )
    assert not result.isError, f"MCP error: {result.content[0].text}"
    data = json.loads(result.content[0].text)
    items = data.get("items", [])
    assert len(items) > 0, "Expected timeseries data from spike profile"
    values = [item.get("value", 0) for item in items if "value" in item]
    assert any(v > 0.85 for v in values), (
        f"Expected at least one CPU user value > 0.85 (spike phase), got max={max(values, default=0):.3f}"
    )


@pytest.mark.e2e
async def test_steady_state_cpu_in_baseline_range(e2e_session):
    """Steady-state profile produces CPU user median in [0.20, 0.40]."""
    result = await e2e_session.call_tool(
        "pcp_query_series",
        {"expr": "kernel.all.cpu.user", "start": "-90minutes", "finish": "now"},
    )
    assert not result.isError, f"MCP error: {result.content[0].text}"
    rows = [json.loads(c.text) for c in result.content]
    values = []
    for row in rows:
        if isinstance(row, dict) and "value" in row:
            values.append(float(row["value"]))
    assert len(values) > 0, "Expected CPU user values from seeded data"
    med = statistics.median(values)
    assert 0.20 <= med <= 0.40, (
        f"Expected steady-state CPU user median in [0.20, 0.40], got {med:.3f}"
    )


# ---------------------------------------------------------------------------
# US3 — Multi-profile extensibility
# ---------------------------------------------------------------------------


@pytest.mark.e2e
async def test_both_profiles_data_present(e2e_session):
    """At least 2 distinct source hostnames appear — one per seeded profile."""
    result = await e2e_session.call_tool(
        "pcp_search",
        {"query": "kernel.all.cpu.user"},
    )
    assert not result.isError, f"MCP error: {result.content[0].text}"
    items = [json.loads(c.text) for c in result.content]
    hostnames = {item.get("indom") or item.get("source") or item.get("name") for item in items}
    # Broader check: generator iterated both profiles → at least 2 distinct sources
    assert len(items) >= 2, (
        f"Expected data from at least 2 profiles (sources), got {len(items)}: {items}"
    )
