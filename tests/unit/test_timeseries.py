"""Tests for pcp_fetch_timeseries — SQLite sink mode."""

from __future__ import annotations

import httpx
import pytest
import respx

from pmmcp.client import PmproxyClient
from pmmcp.config import PmproxyConfig
from pmmcp.session_db import SessionDB

PMPROXY_BASE = "http://localhost:44322"
TEST_SERIES = "605fc77742cd0317597291329561ac4e50c0dd12"


@pytest.fixture
def config():
    return PmproxyConfig(url=PMPROXY_BASE, timeout=5.0)


@pytest.fixture
async def client(config):
    c = PmproxyClient(config)
    yield c
    await c.close()


@pytest.fixture
async def session_db(tmp_path):
    db = SessionDB(tmp_path / "test.db")
    await db.open()
    yield db
    await db.close(delete=True)


def _make_values(series_id: str, count: int = 3) -> list[dict]:
    return [
        {"series": series_id, "timestamp": 1547483646.0 + i * 60, "value": str(i * 10)}
        for i in range(count)
    ]


def _mock_series_endpoints(series_id: str, metric_name: str, count: int = 3):
    """Set up standard respx mocks for a single series fetch."""
    respx.get(f"{PMPROXY_BASE}/series/query").mock(
        return_value=httpx.Response(200, json=[series_id])
    )
    respx.get(f"{PMPROXY_BASE}/series/values").mock(
        return_value=httpx.Response(200, json=_make_values(series_id, count))
    )
    respx.get(f"{PMPROXY_BASE}/series/labels").mock(
        return_value=httpx.Response(
            200, json=[{"series": series_id, "labels": {"metric.name": metric_name}}]
        )
    )
    respx.get(f"{PMPROXY_BASE}/series/instances").mock(
        return_value=httpx.Response(200, json=[])
    )


@respx.mock
async def test_fetch_writes_to_sqlite(client, session_db):
    """pcp_fetch_timeseries writes data to SQLite, not returned inline."""
    _mock_series_endpoints(TEST_SERIES, "kernel.all.load")

    from pmmcp.tools.timeseries import _fetch_timeseries_impl

    result = await _fetch_timeseries_impl(
        client, session_db,
        names=["kernel.all.load"],
        start="-1hour", end="now", interval="auto",
        host="", instances=[], limit=500, offset=0, expr="",
    )
    assert not result.get("isError"), f"Got error: {result}"
    assert "row_count" in result
    assert result["row_count"] == 3
    assert "kernel.all.load" in result["metrics"]

    # No raw samples in return
    assert "items" not in result
    assert "samples" not in result

    # Data is in SQLite
    rows = await session_db.query("SELECT * FROM timeseries ORDER BY timestamp")
    assert len(rows) == 3
    assert rows[0]["metric"] == "kernel.all.load"


@respx.mock
async def test_fetch_returns_window_metadata(client, session_db):
    """Return includes window metadata and hint."""
    _mock_series_endpoints(TEST_SERIES, "cpu.user")

    from pmmcp.tools.timeseries import _fetch_timeseries_impl

    result = await _fetch_timeseries_impl(
        client, session_db,
        names=["cpu.user"],
        start="-1hour", end="now", interval="15s",
        host="", instances=[], limit=500, offset=0, expr="",
    )
    assert "window" in result
    assert result["window"]["start"] == "-1hour"
    assert result["window"]["end"] == "now"
    assert "hint" in result


@respx.mock
async def test_fetch_auto_interval_resolved(client, session_db):
    """interval='auto' is resolved before calling pmproxy."""
    _mock_series_endpoints(TEST_SERIES, "kernel.all.load")

    from pmmcp.tools.timeseries import _fetch_timeseries_impl

    await _fetch_timeseries_impl(
        client, session_db,
        names=["kernel.all.load"],
        start="-1hour", end="now", interval="auto",
        host="", instances=[], limit=500, offset=0, expr="",
    )
    for call in respx.calls:
        if "/series/values" in str(call.request.url):
            assert "auto" not in str(call.request.url)


@respx.mock
async def test_fetch_multi_metric_queries_separately(client, session_db):
    """Each metric name is queried individually."""
    SERIES_A = "a" * 40
    SERIES_B = "b" * 40

    query_route = respx.get(f"{PMPROXY_BASE}/series/query").mock(
        side_effect=[
            httpx.Response(200, json=[SERIES_A]),
            httpx.Response(200, json=[SERIES_B]),
        ]
    )
    respx.get(f"{PMPROXY_BASE}/series/values").mock(
        side_effect=[
            httpx.Response(200, json=_make_values(SERIES_A)),
            httpx.Response(200, json=_make_values(SERIES_B)),
        ]
    )
    respx.get(f"{PMPROXY_BASE}/series/labels").mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{PMPROXY_BASE}/series/instances").mock(return_value=httpx.Response(200, json=[]))

    from pmmcp.tools.timeseries import _fetch_timeseries_impl

    result = await _fetch_timeseries_impl(
        client, session_db,
        names=["cpu.user", "cpu.sys"],
        start="-1hour", end="now", interval="5min",
        host="", instances=[], limit=500, offset=0, expr="",
    )
    assert query_route.call_count == 2
    assert result["row_count"] == 6


@respx.mock
async def test_fetch_with_expr_overrides_names(client, session_db):
    """When expr is provided, it is used instead of names."""
    _mock_series_endpoints(TEST_SERIES, "kernel.percpu.cpu.user")

    from pmmcp.tools.timeseries import _fetch_timeseries_impl

    result = await _fetch_timeseries_impl(
        client, session_db,
        names=[],
        start="-1hour", end="now", interval="15s",
        host="", instances=[], limit=500, offset=0,
        expr='kernel.percpu.cpu.user{hostname=="web-01"}',
    )
    assert not result.get("isError"), f"Got error: {result}"
    assert result["row_count"] == 3

    query_call = [c for c in respx.calls if "/series/query" in str(c.request.url)][0]
    assert "kernel.percpu.cpu.user" in str(query_call.request.url)


@respx.mock
async def test_fetch_accumulates_across_calls(client, session_db):
    """Multiple fetch calls accumulate data in the same session DB."""
    _mock_series_endpoints(TEST_SERIES, "metric.a", count=2)

    from pmmcp.tools.timeseries import _fetch_timeseries_impl

    await _fetch_timeseries_impl(
        client, session_db,
        names=["metric.a"],
        start="-1hour", end="now", interval="15s",
        host="", instances=[], limit=500, offset=0, expr="",
    )

    SERIES_B = "b" * 40
    respx.reset()
    _mock_series_endpoints(SERIES_B, "metric.b", count=3)

    await _fetch_timeseries_impl(
        client, session_db,
        names=["metric.b"],
        start="-1hour", end="now", interval="15s",
        host="", instances=[], limit=500, offset=0, expr="",
    )

    rows = await session_db.query("SELECT COUNT(*) as cnt FROM timeseries")
    assert rows[0]["cnt"] == 5


@respx.mock
async def test_fetch_connection_error_returns_mcp_error(client, session_db):
    """Connection error is surfaced as MCP error."""
    respx.get(f"{PMPROXY_BASE}/series/query").mock(
        side_effect=httpx.RemoteProtocolError("Server disconnected")
    )

    from pmmcp.tools.timeseries import _fetch_timeseries_impl

    result = await _fetch_timeseries_impl(
        client, session_db,
        names=["cpu.user"],
        start="-1hour", end="now", interval="15s",
        host="", instances=[], limit=500, offset=0, expr="",
    )
    assert result.get("isError") is True
    text = result["content"][0]["text"]
    assert "connection" in text.lower() or "disconnected" in text.lower()


@respx.mock
async def test_fetch_timeout_returns_mcp_error(client, session_db):
    """Timeout is surfaced as MCP error."""
    respx.get(f"{PMPROXY_BASE}/series/query").mock(
        side_effect=httpx.ReadTimeout("Timeout")
    )

    from pmmcp.tools.timeseries import _fetch_timeseries_impl

    result = await _fetch_timeseries_impl(
        client, session_db,
        names=["cpu.user"],
        start="-1hour", end="now", interval="15s",
        host="", instances=[], limit=500, offset=0, expr="",
    )
    assert result.get("isError") is True
    text = result["content"][0]["text"]
    assert "timeout" in text.lower()


@respx.mock
async def test_fetch_natural_sample_cap(client, session_db):
    """Samples sent to pmproxy are capped at natural fit (window/interval)."""
    _mock_series_endpoints(TEST_SERIES, "cpu.user")

    from pmmcp.tools.timeseries import _fetch_timeseries_impl

    await _fetch_timeseries_impl(
        client, session_db,
        names=["cpu.user"],
        start="-1hour", end="now", interval="15s",
        host="", instances=[], limit=500, offset=0, expr="",
    )
    import re
    for call in respx.calls:
        if "/series/values" in str(call.request.url):
            url_str = str(call.request.url)
            m = re.search(r"samples=(\d+)", url_str)
            if m:
                assert int(m.group(1)) == 240, f"Expected 240 natural samples, got {m.group(1)}"
