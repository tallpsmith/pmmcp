# Phase 2: SQLite Sink Design

> Approved 2026-03-09. Replaces Phase 2 (Tasks 13-18) from the original hardening plan.

## Problem

`pcp_fetch_timeseries` returns raw samples into Claude's context window. Broad investigations waste thousands of tokens on numbers nobody reads. The LLM needs data out-of-band so it can fetch broadly and analyse selectively.

## Design Decisions

1. **SQLite is the standard storage path** — not optional, not a parallel tool. `pcp_fetch_timeseries` writes to SQLite and returns metadata only.
2. **Drop `pcp_query_series`** — consolidate into `pcp_fetch_timeseries` with an optional `expr` parameter. Two tools total: fetch, then query.
3. **Session-scoped DB with TTL cleanup** — dedicated directory (`~/.pmmcp/sessions/`), background purge on startup deletes files older than configurable TTL. Current session DB deleted on shutdown.

## Tool Surface (2 tools)

### `pcp_fetch_timeseries` (modified)

Same name, same parameters, plus optional `expr`. New return shape:

```python
# Parameters (unchanged + expr)
names: list[str]          # metric names
start: str = "-1hour"
end: str = "now"
interval: str = "auto"
host: str = ""
instances: list[str] = []
limit: int = 500
offset: int = 0
expr: str = ""            # NEW: raw PCP series expression (overrides names)

# Return (NEW — metadata only)
{
    "row_count": 720,
    "metrics": ["kernel.all.cpu.user"],
    "window": {"start": "-6hours", "end": "now", "interval": "5min"},
    "hint": "Use pcp_query_sqlite to analyse this data"
}
```

Multiple calls accumulate in the same session DB. Fetch different metrics or time windows, then JOIN/compare with SQL.

### `pcp_query_sqlite` (new)

```python
# Parameters
sql: str              # SELECT query (read-only; mutating statements rejected)
row_limit: int = 500  # max rows returned

# Return
{
    "rows": [{"metric": "cpu.user", "avg_val": 42.75}, ...],
    "row_count": 1,
    "truncated": false
}
```

Rejects INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/ATTACH/DETACH via first-keyword check.

## Schema

```sql
CREATE TABLE timeseries (
    metric    TEXT NOT NULL,
    instance  TEXT,
    host      TEXT,
    timestamp REAL NOT NULL,
    value     REAL NOT NULL
);
CREATE INDEX idx_ts_metric ON timeseries(metric);
CREATE INDEX idx_ts_timestamp ON timeseries(timestamp);
CREATE INDEX idx_ts_host ON timeseries(host);
```

## Components

### `src/pmmcp/session_db.py` (new)

```python
class SessionDB:
    def __init__(self, db_path: Path) -> None: ...
    async def open(self) -> None: ...
    async def close(self, delete: bool = True) -> None: ...
    async def insert_timeseries(self, rows: list[dict]) -> int: ...
    async def query(self, sql: str, params: tuple = ()) -> list[dict]: ...
    @property
    def path(self) -> Path: ...
```

- Constructor takes explicit `Path` (server picks it using session directory + UUID)
- `close(delete=True)` unlinks the file by default
- `query()` returns `list[dict]` with column names as keys

### Config additions (`src/pmmcp/config.py`)

```python
session_dir: Path = Path("~/.pmmcp/sessions")  # env: PMPROXY_SESSION_DIR
session_ttl_hours: int = 24                      # env: PMPROXY_SESSION_TTL_HOURS
```

### Server lifespan changes (`src/pmmcp/server.py`)

**Startup:**
1. `session_dir.expanduser().mkdir(parents=True, exist_ok=True)`
2. Fire-and-forget `_purge_stale_sessions()` — scans directory, unlinks `.db` files older than TTL
3. Create `SessionDB(session_dir / f"{uuid4()}.db")`, call `open()`
4. Expose via `get_session_db()` (same pattern as `get_client()`)

**Shutdown:**
1. Cancel health monitor (existing)
2. `await session_db.close(delete=True)` — close + unlink
3. Close httpx client (existing)

### Purge task

```python
async def _purge_stale_sessions(session_dir: Path, ttl_hours: int) -> None:
    cutoff = time.time() - (ttl_hours * 3600)
    for db_file in session_dir.glob("*.db"):
        if db_file.stat().st_mtime < cutoff:
            db_file.unlink()
            logger.info("purged stale session: %s", db_file.name)
```

Runs once at startup. Not on a loop. Crashes leave orphans; next startup cleans them.

## What Doesn't Change

Internal tools (anomaly, comparison, correlation, scanning, ranking, investigate) use `_fetch_window` directly. They need in-memory data for their own analysis. No SQLite involvement.

## Files Summary

| File | Action | Purpose |
|------|--------|---------|
| `pyproject.toml` | modify | add `aiosqlite>=0.20` |
| `src/pmmcp/session_db.py` | create | SessionDB class |
| `src/pmmcp/config.py` | modify | add `session_dir`, `session_ttl_hours` |
| `src/pmmcp/server.py` | modify | lifespan: create/destroy SessionDB, purge task, `get_session_db()` |
| `src/pmmcp/tools/timeseries.py` | modify | rewrite to sink into SQLite, add `expr` param, drop `pcp_query_series` |
| `src/pmmcp/tools/sqlite_sink.py` | create | `pcp_query_sqlite` tool |
| `src/pmmcp/tools/__init__.py` | modify | register `sqlite_sink` |
