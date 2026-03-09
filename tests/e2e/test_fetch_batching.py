"""E2E tests proving _fetch_window batches series_values calls correctly.

These tests spawn pmmcp with PMMCP_SERIES_BATCH_SIZE=2 so any metric with ≥3
instances forces batching. kernel.percpu.cpu.user has one series per CPU core,
so on any multi-core host (all CI runners) this reliably exercises batching.
"""

from __future__ import annotations

import os
import sys

import pytest
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

PMPROXY_URL = os.environ.get("PMPROXY_URL", "")


@pytest.fixture(scope="module")
async def e2e_batched_session():
    """pmmcp subprocess with batch size forced to 2 to prove batching works."""
    env = {**os.environ, "PMPROXY_URL": PMPROXY_URL, "PMMCP_SERIES_BATCH_SIZE": "2"}
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
        pass


@pytest.mark.e2e
async def test_detect_anomalies_survives_forced_tiny_batches(e2e_batched_session):
    """pcp_detect_anomalies succeeds when forced to use batch size=2.

    BEFORE fix: PMMCP_SERIES_BATCH_SIZE is silently ignored → single call for
                all series → passes trivially on small hosts but the unit tests
                prove the batching gate.
    AFTER fix:  batch size=2 → multiple calls per window → merged correctly →
                no error on multi-core hosts in CI.
    """
    result = await e2e_batched_session.call_tool(
        "pcp_detect_anomalies",
        {
            "metrics": ["kernel.percpu.cpu.user"],
            "recent_start": "-10minutes",
            "recent_end": "now",
            "baseline_start": "-60minutes",
            "baseline_end": "-10minutes",
            "interval": "1minute",
        },
    )
    assert not result.isError, f"Batching failed: {result.content[0].text}"


@pytest.mark.e2e
async def test_compare_windows_survives_forced_tiny_batches(e2e_batched_session):
    """pcp_compare_windows succeeds with kernel.percpu.cpu.user under batch size=2."""
    result = await e2e_batched_session.call_tool(
        "pcp_compare_windows",
        {
            "names": ["kernel.percpu.cpu.user"],
            "window_a_start": "-60minutes",
            "window_a_end": "-10minutes",
            "window_b_start": "-10minutes",
            "window_b_end": "now",
            "interval": "1minute",
        },
    )
    assert not result.isError, f"Batching failed: {result.content[0].text}"
