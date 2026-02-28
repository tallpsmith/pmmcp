from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from mcp.server.fastmcp import FastMCP

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

# Side-effect imports: triggers @mcp.tool registration for all tool modules.
# This import MUST be at the bottom to avoid circular import issues.
import pmmcp.prompts  # noqa: E402, F401
import pmmcp.tools  # noqa: E402, F401
