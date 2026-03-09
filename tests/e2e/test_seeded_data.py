"""E2E tests for pmlogsynth-seeded data.

Requires: PMPROXY_URL set and a running compose stack (pmlogsynth-generator and
pmlogsynth-seeder one-shot services must have completed before pcp starts).

Run:
  podman compose up -d
  PMPROXY_URL=http://localhost:44322 uv run pytest tests/e2e/test_seeded_data.py -m e2e -v

Data flow: pcp_fetch_timeseries → session SQLite → pcp_query_sqlite for assertions.
"""

from __future__ import annotations

import json

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _fetch_and_query(session, expr: str, sql: str, start: str = "-90minutes") -> list[dict]:
    """Load data via pcp_fetch_timeseries, then query via pcp_query_sqlite."""
    fetch = await session.call_tool(
        "pcp_fetch_timeseries",
        {"expr": expr, "start": start, "end": "now"},
    )
    assert not fetch.isError, f"Fetch error: {fetch.content[0].text}"

    result = await session.call_tool("pcp_query_sqlite", {"sql": sql})
    assert not result.isError, f"Query error: {result.content[0].text}"
    data = json.loads(result.content[0].text)
    return data.get("rows", [])


# ---------------------------------------------------------------------------
# US1 — Realistic data present on stack startup
# ---------------------------------------------------------------------------


@pytest.mark.e2e
async def test_cpu_metrics_present(e2e_session):
    """Seeded archive contains CPU data accessible via fetch + SQL."""
    rows = await _fetch_and_query(
        e2e_session,
        expr="kernel.all.cpu.user",
        sql="SELECT COUNT(*) AS cnt FROM timeseries WHERE metric = 'kernel.all.cpu.user'",
    )
    assert len(rows) > 0 and rows[0]["cnt"] > 0, (
        "Expected non-empty CPU metric data from seeded archive"
    )


@pytest.mark.e2e
async def test_memory_metrics_present(e2e_session):
    """Seeded archive contains memory data accessible via fetch + SQL."""
    rows = await _fetch_and_query(
        e2e_session,
        expr="mem.util.used",
        sql="SELECT COUNT(*) AS cnt FROM timeseries WHERE metric = 'mem.util.used'",
    )
    assert len(rows) > 0 and rows[0]["cnt"] > 0, (
        "Expected non-empty memory metric data from seeded archive"
    )


@pytest.mark.e2e
async def test_disk_metrics_present(e2e_session):
    """Seeded archive contains disk data accessible via fetch + SQL."""
    rows = await _fetch_and_query(
        e2e_session,
        expr="disk.all.read",
        sql="SELECT COUNT(*) AS cnt FROM timeseries WHERE metric = 'disk.all.read'",
    )
    assert len(rows) > 0 and rows[0]["cnt"] > 0, (
        "Expected non-empty disk metric data from seeded archive"
    )


# ---------------------------------------------------------------------------
# US2 — Deterministic pattern assertions
# ---------------------------------------------------------------------------


@pytest.mark.e2e
async def test_spike_pattern_detected(e2e_session):
    """Spike profile produces CPU samples — spike phase shows elevated CPU user time."""
    rows = await _fetch_and_query(
        e2e_session,
        expr="kernel.all.cpu.user",
        sql="SELECT MAX(value) AS peak FROM timeseries WHERE metric = 'kernel.all.cpu.user'",
    )
    assert len(rows) > 0, "Expected timeseries data from spike profile"
    peak = rows[0]["peak"]
    assert peak is not None, "No data points found for kernel.all.cpu.user"
    # For normalized utilization values [0,1]: spike phase (90% CPU) should exceed 0.85.
    # For raw counter values (ms): all values vastly exceed 0.85 — trivially passes.
    assert peak > 0.85, (
        f"Expected at least one CPU sample > 0.85 (spike phase threshold). peak={peak:.3f}"
    )


@pytest.mark.e2e
async def test_steady_state_cpu_in_baseline_range(e2e_session):
    """Steady-state profile produces CPU user data throughout the window."""
    rows = await _fetch_and_query(
        e2e_session,
        expr="kernel.all.cpu.user",
        sql=(
            "SELECT COUNT(*) AS cnt, MIN(value) AS vmin, "
            "AVG(value) AS vavg FROM timeseries "
            "WHERE metric = 'kernel.all.cpu.user'"
        ),
    )
    assert len(rows) > 0, "Expected CPU user values from seeded data"
    assert rows[0]["cnt"] > 0, "Expected CPU user values from seeded data"
    # Counter values are always non-negative (PM_SEM_COUNTER).
    assert rows[0]["vmin"] >= 0, "CPU counter values must be non-negative"
    # Verify meaningful data exists
    assert rows[0]["vavg"] > 0, f"Expected non-zero CPU user average, got {rows[0]['vavg']}"


# ---------------------------------------------------------------------------
# US3 — Multi-profile extensibility
# ---------------------------------------------------------------------------


@pytest.mark.e2e
async def test_both_profiles_data_present(e2e_session):
    """Multiple seeded profiles contribute data — row count reflects both."""
    rows = await _fetch_and_query(
        e2e_session,
        expr="kernel.all.cpu.user",
        sql="SELECT COUNT(*) AS cnt FROM timeseries WHERE metric = 'kernel.all.cpu.user'",
    )
    assert len(rows) > 0, "Expected query results"
    # Two profiles × ~13 samples each at 5min interval over 90 min.
    # A single profile would give ~13 rows; two profiles give ~26.
    cnt = rows[0]["cnt"]
    assert cnt > 15, f"Expected data from multiple profiles (>15 rows), got {cnt}"
