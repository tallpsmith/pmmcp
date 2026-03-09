from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from pmmcp import __version__
from pmmcp.client import PmproxyClient
from pmmcp.session_db import SessionDB

if TYPE_CHECKING:
    from pmmcp.config import PmproxyConfig

logger = logging.getLogger(__name__)

# Module-level config and client; set before mcp.run() is called
_config: PmproxyConfig | None = None
_client: PmproxyClient | None = None
_session_db: SessionDB | None = None


def get_client() -> PmproxyClient:
    """Return the shared PmproxyClient instance. Raises if not initialized."""
    if _client is None:
        raise RuntimeError("pmmcp client not initialized — server has not started")
    return _client


def get_session_db() -> SessionDB:
    """Return the session SQLite DB. Raises if not initialized."""
    if _session_db is None:
        raise RuntimeError("session DB not initialized — server has not started")
    return _session_db


async def _health_monitor(client: PmproxyClient, config) -> None:
    """Background task: probe pmproxy and log health state on each interval."""
    health_logger = logging.getLogger("pmmcp.health")
    url = str(config.url)
    while True:
        ok, error = await client.probe()
        if ok:
            health_logger.info("pmproxy healthy (url=%s)", url)
        else:
            health_logger.warning("pmproxy unreachable (url=%s, error=%s)", url, error)
        await asyncio.sleep(config.health_interval)


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
        _config.url,
        _session_db.path,
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


mcp = FastMCP("pmmcp", lifespan=_lifespan)


async def _healthcheck_impl(client: PmproxyClient) -> Response:
    """Pure healthcheck logic — testable without a live HTTP request."""
    t0 = time.monotonic()
    ok, error = await client.probe()
    latency_ms = round((time.monotonic() - t0) * 1000, 1)

    pmproxy_url = str(client._config.url)

    if ok:
        return JSONResponse(
            {
                "status": "ok",
                "pmproxy_url": pmproxy_url,
                "connection_ok": True,
                "pmmcp_version": __version__,
                "probe_latency_ms": latency_ms,
            },
            status_code=200,
        )

    return JSONResponse(
        {
            "status": "error",
            "pmproxy_url": pmproxy_url,
            "connection_ok": False,
            "error": error,
            "pmmcp_version": __version__,
        },
        status_code=503,
    )


@mcp.custom_route("/healthcheck", methods=["GET"])
async def healthcheck(request: Request) -> Response:
    return await _healthcheck_impl(get_client())


# Side-effect imports: triggers @mcp.tool registration for all tool modules.
# This import MUST be at the bottom to avoid circular import issues.
import pmmcp.prompts  # noqa: E402, F401
import pmmcp.tools  # noqa: E402, F401
