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
