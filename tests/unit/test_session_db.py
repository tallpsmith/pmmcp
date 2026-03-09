"""Tests for session SQLite database lifecycle."""

import aiosqlite
import pytest

from pmmcp.session_db import SessionDB


@pytest.fixture
async def db(tmp_path):
    db = SessionDB(tmp_path / "test.db")
    await db.open()
    yield db
    await db.close(delete=False)


async def test_open_creates_file_and_schema(tmp_path):
    """SessionDB creates a file and initialises the timeseries table."""
    db = SessionDB(tmp_path / "test.db")
    await db.open()
    assert db.path.exists()

    async with aiosqlite.connect(db.path) as conn:
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='timeseries'"
        )
        row = await cursor.fetchone()
        assert row is not None

    await db.close(delete=False)


async def test_close_with_delete_removes_file(tmp_path):
    """close(delete=True) removes the database file."""
    db = SessionDB(tmp_path / "test.db")
    await db.open()
    path = db.path
    assert path.exists()
    await db.close(delete=True)
    assert not path.exists()


async def test_close_without_delete_keeps_file(tmp_path):
    """close(delete=False) keeps the database file."""
    db = SessionDB(tmp_path / "test.db")
    await db.open()
    path = db.path
    await db.close(delete=False)
    assert path.exists()


async def test_insert_and_query(db):
    """Can insert rows and query them back."""
    await db.insert_timeseries([
        {"metric": "cpu.user", "instance": None, "host": "web-01", "timestamp": 1000.0, "value": 42.5},
        {"metric": "cpu.user", "instance": None, "host": "web-01", "timestamp": 1001.0, "value": 43.0},
        {"metric": "mem.free", "instance": None, "host": "web-01", "timestamp": 1000.0, "value": 8192.0},
    ])

    rows = await db.query("SELECT metric, AVG(value) as avg_val FROM timeseries GROUP BY metric ORDER BY metric")
    assert len(rows) == 2
    assert rows[0]["metric"] == "cpu.user"
    assert abs(rows[0]["avg_val"] - 42.75) < 0.01
    assert rows[1]["metric"] == "mem.free"


async def test_insert_returns_count(db):
    """insert_timeseries returns the number of rows inserted."""
    count = await db.insert_timeseries([
        {"metric": "x", "instance": None, "host": None, "timestamp": 1.0, "value": 1.0},
        {"metric": "y", "instance": None, "host": None, "timestamp": 2.0, "value": 2.0},
    ])
    assert count == 2


async def test_query_returns_column_names(db):
    """Query results include column names as dict keys."""
    await db.insert_timeseries([
        {"metric": "x", "instance": "i1", "host": "h1", "timestamp": 1.0, "value": 1.0},
    ])
    rows = await db.query("SELECT metric, instance, host, timestamp, value FROM timeseries")
    assert rows[0].keys() == {"metric", "instance", "host", "timestamp", "value"}


async def test_query_empty_table(db):
    """Query against empty table returns empty list."""
    rows = await db.query("SELECT * FROM timeseries")
    assert rows == []
