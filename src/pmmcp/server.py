from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from pmmcp import __version__
from pmmcp.client import PmproxyClient

if TYPE_CHECKING:
    from pmmcp.config import PmproxyConfig

logger = logging.getLogger(__name__)

# Module-level config and client; set before mcp.run() is called
_config: PmproxyConfig | None = None
_client: PmproxyClient | None = None


def get_client() -> PmproxyClient:
    """Return the shared PmproxyClient instance. Raises if not initialized."""
    if _client is None:
        raise RuntimeError("pmmcp client not initialized — server has not started")
    return _client


@asynccontextmanager
async def _lifespan(app: FastMCP) -> AsyncIterator[None]:
    global _client
    assert _config is not None, "Config not set — call server._config = ... before mcp.run()"
    _client = PmproxyClient(_config)
    logger.info("pmmcp starting, pmproxy URL: %s", _config.url)
    try:
        yield
    finally:
        await _client.close()
        _client = None
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
