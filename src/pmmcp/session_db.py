"""Session-scoped SQLite database for timeseries data."""

from __future__ import annotations

from pathlib import Path

import aiosqlite

_SCHEMA = """
CREATE TABLE IF NOT EXISTS timeseries (
    metric    TEXT NOT NULL,
    instance  TEXT,
    host      TEXT,
    timestamp REAL NOT NULL,
    value     REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ts_metric ON timeseries(metric);
CREATE INDEX IF NOT EXISTS idx_ts_timestamp ON timeseries(timestamp);
CREATE INDEX IF NOT EXISTS idx_ts_host ON timeseries(host);
"""


class SessionDB:
    """Lightweight wrapper around a session-scoped SQLite file."""

    def __init__(self, db_path: Path) -> None:
        self._path = db_path
        self._conn: aiosqlite.Connection | None = None

    @property
    def path(self) -> Path:
        return self._path

    async def open(self) -> None:
        self._conn = await aiosqlite.connect(self._path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(_SCHEMA)
        await self._conn.commit()

    async def close(self, delete: bool = True) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None
        if delete and self._path.exists():
            self._path.unlink()

    async def insert_timeseries(self, rows: list[dict]) -> int:
        """Insert rows into the timeseries table. Returns count inserted."""
        assert self._conn is not None, "SessionDB not open"
        await self._conn.executemany(
            "INSERT INTO timeseries (metric, instance, host, timestamp, value)"
            " VALUES (?, ?, ?, ?, ?)",
            [
                (r["metric"], r.get("instance"), r.get("host"), r["timestamp"], r["value"])
                for r in rows
            ],
        )
        await self._conn.commit()
        return len(rows)

    async def query(self, sql: str, params: tuple = ()) -> list[dict]:
        """Execute a SELECT and return rows as dicts."""
        assert self._conn is not None, "SessionDB not open"
        cursor = await self._conn.execute(sql, params)
        rows = await cursor.fetchall()
        if not rows:
            return []
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
