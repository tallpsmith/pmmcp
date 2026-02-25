"""E2E test gating and subprocess harness fixtures."""

from __future__ import annotations

import os
import sys

import pytest
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

PMPROXY_URL = os.environ.get("PMPROXY_URL")
SKIP_E2E = os.environ.get("SKIP_E2E", "0") == "1"


def pytest_collection_modifyitems(items):
    """Gate E2E tests: skip on SKIP_E2E=1, xfail when PMPROXY_URL is missing."""
    for item in items:
        if "e2e" in item.nodeid:
            if SKIP_E2E:
                item.add_marker(pytest.mark.skip(reason="E2E opt-out: SKIP_E2E=1"))
            elif not PMPROXY_URL:
                item.add_marker(
                    pytest.mark.xfail(
                        strict=True,
                        reason=(
                            "PMPROXY_URL is required for E2E tests. "
                            "Set SKIP_E2E=1 to explicitly opt out."
                        ),
                    )
                )


@pytest.fixture(scope="session")
async def e2e_session():
    """Session-scoped MCP ClientSession backed by a real pmmcp subprocess over stdio."""
    env = dict(os.environ)
    if PMPROXY_URL:
        env["PMPROXY_URL"] = PMPROXY_URL

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "pmmcp"],
        env=env,
    )
    try:
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as session:
                await session.initialize()
                yield session
    except RuntimeError:
        # pytest-asyncio tears down session fixtures in a different asyncio task
        # than the one anyio used to enter its cancel scopes, producing a benign
        # "Attempted to exit cancel scope in a different task" RuntimeError.
        # All tests have already run at this point; suppress and move on.
        pass
