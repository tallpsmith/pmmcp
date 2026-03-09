"""Tests for pcp_query_sqlite tool."""

import pytest

from pmmcp.session_db import SessionDB
from pmmcp.tools.sqlite_sink import _query_sqlite_impl


@pytest.fixture
async def session_db(tmp_path):
    db = SessionDB(tmp_path / "test.db")
    await db.open()
    await db.insert_timeseries([
        {"metric": "cpu.user", "instance": None, "host": "web-01", "timestamp": 1000.0, "value": 10.0},
        {"metric": "cpu.user", "instance": None, "host": "web-01", "timestamp": 1001.0, "value": 20.0},
        {"metric": "cpu.user", "instance": None, "host": "web-01", "timestamp": 1002.0, "value": 30.0},
        {"metric": "mem.free", "instance": None, "host": "web-01", "timestamp": 1000.0, "value": 8192.0},
    ])
    yield db
    await db.close(delete=True)


async def test_basic_select(session_db):
    """Simple SELECT COUNT works."""
    result = await _query_sqlite_impl(session_db, "SELECT COUNT(*) as cnt FROM timeseries")
    assert result["rows"][0]["cnt"] == 4


async def test_aggregation(session_db):
    """GROUP BY with AVG works."""
    result = await _query_sqlite_impl(
        session_db,
        "SELECT metric, AVG(value) as avg_val FROM timeseries GROUP BY metric ORDER BY metric",
    )
    assert len(result["rows"]) == 2
    assert result["rows"][0]["metric"] == "cpu.user"
    assert abs(result["rows"][0]["avg_val"] - 20.0) < 0.01


async def test_row_limit_enforced(session_db):
    """Row limit truncates results and sets truncated flag."""
    result = await _query_sqlite_impl(session_db, "SELECT * FROM timeseries", row_limit=2)
    assert len(result["rows"]) == 2
    assert result["truncated"] is True


async def test_row_limit_not_truncated(session_db):
    """When results fit within limit, truncated is False."""
    result = await _query_sqlite_impl(session_db, "SELECT * FROM timeseries", row_limit=500)
    assert result["truncated"] is False
    assert result["row_count"] == 4


async def test_rejects_delete(session_db):
    """DELETE statements are rejected."""
    result = await _query_sqlite_impl(session_db, "DELETE FROM timeseries")
    assert result.get("isError") is True


async def test_rejects_drop(session_db):
    """DROP statements are rejected."""
    result = await _query_sqlite_impl(session_db, "DROP TABLE timeseries")
    assert result.get("isError") is True


async def test_rejects_insert(session_db):
    """INSERT statements are rejected."""
    result = await _query_sqlite_impl(
        session_db, "INSERT INTO timeseries VALUES ('x', NULL, NULL, 1.0, 1.0)"
    )
    assert result.get("isError") is True


async def test_rejects_update(session_db):
    """UPDATE statements are rejected."""
    result = await _query_sqlite_impl(session_db, "UPDATE timeseries SET value = 0")
    assert result.get("isError") is True


async def test_invalid_sql_returns_error(session_db):
    """Bad SQL syntax returns MCP error, not an exception."""
    result = await _query_sqlite_impl(session_db, "SELECTT * FORM timeseries")
    assert result.get("isError") is True


async def test_empty_result(session_db):
    """Query that matches nothing returns empty rows."""
    result = await _query_sqlite_impl(
        session_db, "SELECT * FROM timeseries WHERE metric = 'nonexistent'"
    )
    assert result["rows"] == []
    assert result["row_count"] == 0
    assert result["truncated"] is False
