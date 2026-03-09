# SQLite Sink Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Standardize timeseries data storage on a session-scoped SQLite database so raw samples stay out of Claude's context window.

**Architecture:** `pcp_fetch_timeseries` reuses the existing `_fetch_window` pipeline but sinks data into a per-session SQLite DB instead of returning it inline. A new `pcp_query_sqlite` tool provides SQL-based analysis. `pcp_query_series` is removed (consolidated into `pcp_fetch_timeseries` via an optional `expr` parameter). Internal analytical tools (anomaly, comparison, etc.) are unchanged — they use `_fetch_window` directly. Session DBs live in `~/.pmmcp/sessions/` with TTL-based cleanup on startup.

**Tech Stack:** Python 3.11+, aiosqlite, FastMCP, httpx (existing)

**Design doc:** `docs/plans/2026-03-09-sqlite-sink-design.md`

---

## Task 1: Add aiosqlite dependency

**Files:**
- Modify: `pyproject.toml:13-18`

**Step 1: Add dependency**

Add `"aiosqlite>=0.20"` to the dependencies list in `pyproject.toml`:

```toml
dependencies = [
    "mcp[cli]>=1.2.0",
    "pydantic>=2.0",
    "pydantic-settings",
    "httpx>=0.27",
    "aiosqlite>=0.20",
]
```

**Step 2: Sync environment**

Run: `uv sync --extra dev`
Expected: aiosqlite installed successfully

**Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add aiosqlite dependency for session SQLite sink"
```

---

## Task 2: Add session config fields

**Files:**
- Modify: `src/pmmcp/config.py`
- Test: `tests/unit/test_config_session.py` (create)

**Step 1: Write the failing tests**

```python
# tests/unit/test_config_session.py
"""Tests for session-related config fields."""

from pathlib import Path

from pmmcp.config import PmproxyConfig

PMPROXY_BASE = "http://localhost:44322"


def test_session_dir_defaults_to_home():
    """session_dir defaults to ~/.pmmcp/sessions."""
    config = PmproxyConfig(url=PMPROXY_BASE)
    assert config.session_dir == Path("~/.pmmcp/sessions")


def test_session_ttl_hours_defaults_to_24():
    """session_ttl_hours defaults to 24."""
    config = PmproxyConfig(url=PMPROXY_BASE)
    assert config.session_ttl_hours == 24


def test_session_dir_overridable(monkeypatch):
    """session_dir can be overridden via env var."""
    monkeypatch.setenv("PMPROXY_SESSION_DIR", "/tmp/custom-sessions")
    config = PmproxyConfig(url=PMPROXY_BASE)
    assert config.session_dir == Path("/tmp/custom-sessions")


def test_session_ttl_hours_overridable(monkeypatch):
    """session_ttl_hours can be overridden via env var."""
    monkeypatch.setenv("PMPROXY_SESSION_TTL_HOURS", "48")
    config = PmproxyConfig(url=PMPROXY_BASE)
    assert config.session_ttl_hours == 48
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_config_session.py -v`
Expected: FAIL — `session_dir` and `session_ttl_hours` not defined on PmproxyConfig

**Step 3: Write implementation**

Add to `src/pmmcp/config.py` inside `PmproxyConfig`:

```python
from pathlib import Path

class PmproxyConfig(BaseSettings):
    url: AnyHttpUrl
    timeout: float = 30.0
    health_interval: int = 15
    session_dir: Path = Path("~/.pmmcp/sessions")
    session_ttl_hours: int = 24

    model_config = {"env_prefix": "PMPROXY_"}
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_config_session.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/pmmcp/config.py tests/unit/test_config_session.py
git commit -m "feat: add session_dir and session_ttl_hours config fields

Session directory for SQLite DBs with TTL-based cleanup."
```

---

## Task 3: Create SessionDB class

**Files:**
- Create: `src/pmmcp/session_db.py`
- Test: `tests/unit/test_session_db.py` (create)

**Step 1: Write the failing tests**

```python
# tests/unit/test_session_db.py
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
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_session_db.py -v`
Expected: FAIL — `pmmcp.session_db` module doesn't exist

**Step 3: Write implementation**

```python
# src/pmmcp/session_db.py
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
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_session_db.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/pmmcp/session_db.py tests/unit/test_session_db.py
git commit -m "feat: SessionDB — session-scoped SQLite for timeseries data

Schema: timeseries(metric, instance, host, timestamp, value) with indexes.
Supports insert, query, and file cleanup on close."
```

---

## Task 4: Wire SessionDB into server lifespan with stale session purge

**Files:**
- Modify: `src/pmmcp/server.py`
- Test: `tests/unit/test_server_session.py` (create)

**Step 1: Write the failing tests**

```python
# tests/unit/test_server_session.py
"""Tests for session DB lifecycle and stale session purge."""

import time
from pathlib import Path

import pytest

from pmmcp.server import _purge_stale_sessions, get_session_db


def test_get_session_db_raises_outside_lifespan():
    """get_session_db raises RuntimeError when server hasn't started."""
    with pytest.raises(RuntimeError, match="session DB not initialized"):
        get_session_db()


async def test_purge_removes_old_files(tmp_path):
    """Purge deletes .db files older than TTL."""
    old_file = tmp_path / "old.db"
    old_file.touch()
    # Backdate mtime by 2 days
    old_mtime = time.time() - (48 * 3600)
    import os
    os.utime(old_file, (old_mtime, old_mtime))

    fresh_file = tmp_path / "fresh.db"
    fresh_file.touch()

    await _purge_stale_sessions(tmp_path, ttl_hours=24)

    assert not old_file.exists(), "Old file should be purged"
    assert fresh_file.exists(), "Fresh file should be kept"


async def test_purge_ignores_non_db_files(tmp_path):
    """Purge only touches .db files."""
    txt_file = tmp_path / "notes.txt"
    txt_file.touch()
    old_mtime = time.time() - (48 * 3600)
    import os
    os.utime(txt_file, (old_mtime, old_mtime))

    await _purge_stale_sessions(tmp_path, ttl_hours=24)

    assert txt_file.exists(), "Non-.db files should not be purged"


async def test_purge_handles_empty_directory(tmp_path):
    """Purge does not crash on empty directory."""
    await _purge_stale_sessions(tmp_path, ttl_hours=24)
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_server_session.py -v`
Expected: FAIL — `get_session_db` and `_purge_stale_sessions` not defined

**Step 3: Write implementation**

Add to `src/pmmcp/server.py`. Imports to add near the top:

```python
import time
from pathlib import Path
from uuid import uuid4

from pmmcp.session_db import SessionDB
```

Add module-level state and getter after `get_client()`:

```python
_session_db: SessionDB | None = None


def get_session_db() -> SessionDB:
    """Return the session SQLite DB. Raises if not initialized."""
    if _session_db is None:
        raise RuntimeError("session DB not initialized — server has not started")
    return _session_db
```

Add purge function after `_health_monitor`:

```python
async def _purge_stale_sessions(session_dir: Path, ttl_hours: int) -> None:
    """Delete .db files in session_dir older than ttl_hours."""
    cutoff = time.time() - (ttl_hours * 3600)
    for db_file in session_dir.glob("*.db"):
        try:
            if db_file.stat().st_mtime < cutoff:
                db_file.unlink()
                logger.info("purged stale session: %s", db_file.name)
        except OSError:
            pass
```

Update `_lifespan`:

```python
@asynccontextmanager
async def _lifespan(app: FastMCP) -> AsyncIterator[None]:
    global _client, _session_db
    assert _config is not None, "Config not set — call server._config = ... before mcp.run()"

    _client = PmproxyClient(_config)

    # Session DB: ensure directory exists, purge stale files, create new DB
    session_dir = _config.session_dir.expanduser()
    session_dir.mkdir(parents=True, exist_ok=True)
    asyncio.create_task(_purge_stale_sessions(session_dir, _config.session_ttl_hours))
    _session_db = SessionDB(session_dir / f"{uuid4()}.db")
    await _session_db.open()

    logger.info(
        "pmmcp starting, pmproxy URL: %s, session DB: %s",
        _config.url, _session_db.path,
    )
    monitor_task = asyncio.create_task(_health_monitor(_client, _config))
    try:
        yield
    finally:
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass
        await _client.close()
        _client = None
        await _session_db.close(delete=True)
        _session_db = None
        logger.info("pmmcp shutting down")
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_server_session.py -v`
Expected: PASS

**Step 5: Run full test suite**

Run: `uv run pytest --cov=pmmcp --cov-report=term-missing`
Expected: PASS — existing tests unaffected

**Step 6: Commit**

```bash
git add src/pmmcp/server.py tests/unit/test_server_session.py
git commit -m "feat: wire SessionDB into server lifespan with stale session purge

Created on startup in ~/.pmmcp/sessions/<uuid>.db, deleted on shutdown.
Background purge removes .db files older than session_ttl_hours."
```

---

## Task 5: Rewrite `pcp_fetch_timeseries` to sink into SQLite

This is the core change. `_fetch_timeseries_impl` gets `session_db` as a new parameter. Instead of returning `items` with raw samples, it writes to SQLite and returns compact metadata. Also adds `expr` parameter and removes `pcp_query_series`.

**Files:**
- Modify: `src/pmmcp/tools/timeseries.py`
- Modify: `tests/unit/test_timeseries.py` (rewrite tests for new return shape)

**Step 1: Rewrite the tests for new behaviour**

Replace the contents of `tests/unit/test_timeseries.py`:

```python
# tests/unit/test_timeseries.py
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

    # Verify the expr was sent to series/query
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

    # Second fetch (re-mock for different metric)
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
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_timeseries.py -v`
Expected: FAIL — `_fetch_timeseries_impl` signature has changed (missing `session_db`)

**Step 3: Rewrite implementation**

Replace contents of `src/pmmcp/tools/timeseries.py`:

```python
"""pcp_fetch_timeseries — historical time-series data, stored in session SQLite DB."""

from __future__ import annotations

import logging

from pmmcp.client import PmproxyClient, PmproxyConnectionError, PmproxyError, PmproxyTimeoutError
from pmmcp.server import get_client, get_session_db, mcp
from pmmcp.session_db import SessionDB
from pmmcp.tools._errors import _mcp_error
from pmmcp.tools._fetch import _fetch_window
from pmmcp.utils import natural_samples as compute_natural_samples
from pmmcp.utils import resolve_interval

logger = logging.getLogger(__name__)


async def _fetch_timeseries_impl(
    client: PmproxyClient,
    session_db: SessionDB,
    names: list[str],
    start: str,
    end: str,
    interval: str,
    host: str,
    instances: list[str],
    limit: int,
    offset: int,
    expr: str,
) -> dict:
    """Fetch timeseries data and write to session SQLite DB.

    Returns compact metadata — use pcp_query_sqlite to analyse the data.
    """
    resolved = resolve_interval(start, end, interval)
    try:
        effective_samples = min(limit, compute_natural_samples(start, end, resolved))
    except ValueError:
        effective_samples = limit

    # Build expression list: either from explicit expr or from metric names
    if expr:
        exprs = [expr]
    else:
        exprs = [f'{name}{{hostname=="{host}"}}' if host else name for name in names]

    all_rows: list[dict] = []
    metrics_seen: set[str] = set()
    last_error: dict | None = None

    for expression in exprs:
        try:
            _, raw_samples = await _fetch_window(
                client,
                exprs=[expression],
                start=start,
                end=end,
                interval=resolved,
                limit=effective_samples,
            )
        except PmproxyConnectionError as exc:
            last_error = _mcp_error(
                "Connection error",
                f"pmproxy is unreachable: {exc}",
                "Check that pmproxy is running and the URL is correct.",
            )
            continue
        except PmproxyTimeoutError as exc:
            last_error = _mcp_error(
                "Timeout",
                f"pmproxy did not respond in time: {exc}",
                "Try reducing the time window or number of metrics.",
            )
            continue
        except PmproxyError as exc:
            last_error = _mcp_error("pmproxy error", str(exc), "Check the metric name or expression.")
            continue

        for (metric_name, instance), samples in raw_samples.items():
            metrics_seen.add(metric_name)
            for sample in samples:
                all_rows.append({
                    "metric": metric_name,
                    "instance": instance,
                    "host": host or None,
                    "timestamp": sample["timestamp"],
                    "value": sample["value"],
                })

    if not all_rows and last_error:
        return last_error

    if all_rows:
        await session_db.insert_timeseries(all_rows)

    return {
        "row_count": len(all_rows),
        "metrics": sorted(metrics_seen),
        "window": {"start": start, "end": end, "interval": resolved},
        "hint": "Use pcp_query_sqlite to analyse this data",
    }


@mcp.tool()
async def pcp_fetch_timeseries(
    names: list[str] = [],  # noqa: B006
    start: str = "-1hour",
    end: str = "now",
    interval: str = "auto",
    host: str = "",
    instances: list[str] = [],  # noqa: B006
    limit: int = 500,
    offset: int = 0,
    expr: str = "",
) -> dict:
    """Fetch historical time-series data into the session database for SQL analysis.

    Data is stored in the session SQLite DB — use pcp_query_sqlite to analyse it.
    Multiple calls accumulate data: fetch different metrics or time windows, then
    JOIN/compare them with SQL.

    NOT for exploratory investigation — use pcp_quick_investigate for discovery.
    Use for targeted drill-down after anomalies are identified.

    The session DB schema: timeseries(metric TEXT, instance TEXT, host TEXT,
    timestamp REAL, value REAL).

    Auto-interval mapping: <=1h->15s, <=24h->5min, <=7d->1hour, >7d->6hour

    Args:
        names: List of metric names (ignored if expr is provided)
        start: Start time (ISO-8601 or PCP relative e.g. '-6hours', '-7days')
        end: End time (ISO-8601 or 'now')
        interval: Sampling interval (e.g., '15s', '5min', '1hour') or 'auto'
        host: Target hostname or glob (empty queries all hosts)
        instances: Filter to specific instances (empty means all)
        limit: Maximum data points per metric/instance (default 500)
        offset: Pagination offset
        expr: Raw PCP series expression (overrides names if provided)
    """
    return await _fetch_timeseries_impl(
        get_client(),
        get_session_db(),
        names=names,
        start=start,
        end=end,
        interval=interval,
        host=host,
        instances=instances,
        limit=limit,
        offset=offset,
        expr=expr,
    )
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_timeseries.py -v`
Expected: PASS

**Step 5: Run full test suite**

Run: `uv run pytest --cov=pmmcp --cov-report=term-missing`
Expected: Some contract tests may fail (Task 7 fixes those). Unit tests should pass.

**Step 6: Commit**

```bash
git add src/pmmcp/tools/timeseries.py tests/unit/test_timeseries.py
git commit -m "feat: pcp_fetch_timeseries sinks data to session SQLite DB

Returns compact metadata instead of raw samples. Add expr parameter for
raw PCP expressions. Remove pcp_query_series (consolidated into expr param)."
```

---

## Task 6: Create `pcp_query_sqlite` tool

**Files:**
- Create: `src/pmmcp/tools/sqlite_sink.py`
- Test: `tests/unit/test_sqlite_query.py` (create)

**Step 1: Write the failing tests**

```python
# tests/unit/test_sqlite_query.py
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
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_sqlite_query.py -v`
Expected: FAIL — module `pmmcp.tools.sqlite_sink` doesn't exist

**Step 3: Write implementation**

```python
# src/pmmcp/tools/sqlite_sink.py
"""pcp_query_sqlite — SQL interface to the session timeseries database."""

from __future__ import annotations

from pmmcp.server import get_session_db, mcp
from pmmcp.session_db import SessionDB
from pmmcp.tools._errors import _mcp_error

_FORBIDDEN_KEYWORDS = {"INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "ATTACH", "DETACH"}


async def _query_sqlite_impl(
    session_db: SessionDB,
    sql: str,
    row_limit: int = 500,
) -> dict:
    """Execute a read-only SQL query against the session DB."""
    first_word = sql.strip().split()[0].upper() if sql.strip() else ""
    if first_word in _FORBIDDEN_KEYWORDS:
        return _mcp_error(
            "Read-only violation",
            f"Statement type '{first_word}' is not allowed.",
            "Only SELECT queries are permitted against the session DB.",
        )

    try:
        rows = await session_db.query(f"{sql} LIMIT {row_limit + 1}")
    except Exception as exc:
        return _mcp_error("SQL error", str(exc), "Check your SQL syntax.")

    truncated = len(rows) > row_limit
    if truncated:
        rows = rows[:row_limit]

    return {
        "rows": rows,
        "row_count": len(rows),
        "truncated": truncated,
    }


@mcp.tool()
async def pcp_query_sqlite(
    sql: str,
    row_limit: int = 500,
) -> dict:
    """Run a SQL query against the session timeseries database.

    Use after pcp_fetch_timeseries to analyse accumulated data with SQL.
    Multiple pcp_fetch_timeseries calls accumulate data — you can fetch different
    metrics or time windows and then JOIN/compare them.

    Schema: timeseries(metric TEXT, instance TEXT, host TEXT, timestamp REAL, value REAL)

    Example queries:
    - SELECT metric, AVG(value), MAX(value) FROM timeseries GROUP BY metric
    - SELECT metric, value FROM timeseries WHERE timestamp BETWEEN 1000 AND 2000
    - SELECT metric, host, AVG(value) FROM timeseries GROUP BY metric, host
    - SELECT COUNT(DISTINCT metric) as num_metrics FROM timeseries

    Args:
        sql: SELECT query to execute (read-only; INSERT/UPDATE/DELETE rejected)
        row_limit: Maximum rows to return (default 500)
    """
    return await _query_sqlite_impl(get_session_db(), sql=sql, row_limit=row_limit)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_sqlite_query.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/pmmcp/tools/sqlite_sink.py tests/unit/test_sqlite_query.py
git commit -m "feat: pcp_query_sqlite — SQL interface to session timeseries DB

Read-only queries against accumulated timeseries data. Rejects mutating
statements. Row limit prevents context flooding."
```

---

## Task 7: Register sqlite_sink, update contract tests

**Files:**
- Modify: `src/pmmcp/tools/__init__.py`
- Modify: `tests/contract/test_mcp_schemas.py`

**Step 1: Update tool registration**

In `src/pmmcp/tools/__init__.py`, add `sqlite_sink` to the imports:

```python
from pmmcp.tools import (  # noqa: F401
    anomaly,  # noqa: F401
    comparison,  # noqa: F401
    correlation,  # noqa: F401
    derived,
    discovery,  # noqa: F401
    hosts,
    investigate,  # noqa: F401
    live,
    ranking,  # noqa: F401
    scanning,  # noqa: F401
    search,
    sqlite_sink,  # noqa: F401
    timeseries,
)
```

**Step 2: Update contract tests**

In `tests/contract/test_mcp_schemas.py`, update `EXPECTED_TOOLS`:

```python
EXPECTED_TOOLS = {
    "pcp_get_hosts",
    "pcp_discover_metrics",
    "pcp_get_metric_info",
    "pcp_fetch_live",
    "pcp_fetch_timeseries",
    "pcp_query_sqlite",
    "pcp_compare_windows",
    "pcp_search",
    "pcp_derive_metric",
    "pcp_quick_investigate",
}
```

Note: `pcp_query_series` removed, `pcp_query_sqlite` added.

Also update the steering test `test_fetch_timeseries_description_steering` since the description has changed:

```python
def test_fetch_timeseries_description_steering():
    """T014: pcp_fetch_timeseries steers toward pcp_query_sqlite for analysis."""
    desc = _get_tool_description("pcp_fetch_timeseries")
    assert "NOT for exploratory investigation" in desc, f"Missing steering in: {desc}"
    assert "pcp_query_sqlite" in desc, f"Missing pcp_query_sqlite reference in: {desc}"
```

Add a new schema test for `pcp_query_sqlite`:

```python
def test_pcp_query_sqlite_schema():
    """pcp_query_sqlite schema requires 'sql' parameter."""
    tools = {t.name: t for t in srv.mcp._tool_manager.list_tools()}
    tool = tools["pcp_query_sqlite"]
    schema = tool.parameters
    assert "sql" in schema.get("required", []) or "sql" in schema.get("properties", {})
```

Remove `test_query_series_raw_expression` if it exists in the contract tests (it doesn't — it's in `test_timeseries.py` which was already rewritten in Task 5).

**Step 3: Run contract tests**

Run: `uv run pytest tests/contract/ -v`
Expected: PASS

**Step 4: Run full test suite**

Run: `uv run pytest --cov=pmmcp --cov-report=term-missing`
Expected: PASS with ≥80% coverage

**Step 5: Commit**

```bash
git add src/pmmcp/tools/__init__.py tests/contract/test_mcp_schemas.py
git commit -m "chore: register sqlite_sink tool, update contract tests

Remove pcp_query_series from expected tools, add pcp_query_sqlite.
Update description steering test for new pcp_fetch_timeseries wording."
```

---

## Task 8: Pre-push sanity + final review

**Step 1: Run pre-push sanity**

Run: `scripts/pre-push-sanity.sh`
Expected: lint, format, tests all pass with ≥80% coverage

**Step 2: Review all changes**

Run: `git diff main --stat`
Verify only expected files changed.

**Step 3: Fix any issues found**

If lint or tests fail, fix and re-run.

---

## Commit Sequence Summary

| # | Message | Files |
|---|---------|-------|
| 1 | `chore: add aiosqlite dependency` | pyproject.toml, uv.lock |
| 2 | `feat: session_dir and session_ttl_hours config` | config.py, test_config_session.py |
| 3 | `feat: SessionDB — session-scoped SQLite` | session_db.py, test_session_db.py |
| 4 | `feat: wire SessionDB into lifespan + stale purge` | server.py, test_server_session.py |
| 5 | `feat: pcp_fetch_timeseries sinks to SQLite` | timeseries.py, test_timeseries.py |
| 6 | `feat: pcp_query_sqlite` | sqlite_sink.py, test_sqlite_query.py |
| 7 | `chore: register sqlite_sink, update contracts` | __init__.py, test_mcp_schemas.py |
| 8 | (sanity check — no commit) | — |
