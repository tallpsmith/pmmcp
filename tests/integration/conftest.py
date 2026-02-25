"""Integration test fixtures: session-scoped MCP server + per-test ClientSession."""

from __future__ import annotations

import asyncio

import anyio
import pytest
from mcp.client.session import ClientSession
from mcp.shared.message import SessionMessage

import pmmcp.server as server_module
from pmmcp.config import PmproxyConfig

MOCK_PMPROXY_URL = "http://mock-pmproxy:44322"


@pytest.fixture(scope="session")
def mcp_server():
    """One FastMCP instance for the whole integration test session."""
    server_module._config = PmproxyConfig(url=MOCK_PMPROXY_URL, timeout=5.0)
    return server_module.mcp


@pytest.fixture
async def mcp_session(mcp_server):
    """Fresh ClientSession over in-process memory streams for each test.

    Wiring:
      client writes → server reads  (client_w → server_r)
      server writes → client reads  (server_w → client_r)

    NOTE: We call session.__aenter__() manually rather than using `async with
    ClientSession()` to avoid calling __aexit__ in pytest-asyncio 1.x's fixture
    finalizer, which runs in a separate asyncio task and cannot exit anyio
    CancelScopes created in the test's task.  The per-test event loop closes
    after the test and cancels all pending tasks (server + session internals).
    """
    server_w, client_r = anyio.create_memory_object_stream[SessionMessage | Exception](0)
    client_w, server_r = anyio.create_memory_object_stream[SessionMessage | Exception](0)

    init_opts = mcp_server._mcp_server.create_initialization_options()

    asyncio.create_task(
        mcp_server._mcp_server.run(server_r, server_w, init_opts, raise_exceptions=False)
    )

    session = ClientSession(client_r, client_w)
    await session.__aenter__()
    await session.initialize()

    yield session

    # Teardown: no explicit cleanup needed.  pytest-asyncio closes the per-test
    # event loop after each test, which cancels all pending tasks automatically.
