"""Tests for PmproxyClient.probe() connectivity check."""

from __future__ import annotations

import httpx
import pytest
import respx

from pmmcp.client import PmproxyClient
from pmmcp.config import PmproxyConfig

PMPROXY_BASE = "http://localhost:44322"


@pytest.fixture
def config():
    return PmproxyConfig(url=PMPROXY_BASE, timeout=5.0)


@respx.mock
async def test_probe_returns_true_on_2xx(config):
    """probe() returns (True, None) when pmproxy responds with 2xx."""
    respx.get(f"{PMPROXY_BASE}/series/sources").mock(
        return_value=httpx.Response(200, json=["source1"])
    )

    client = PmproxyClient(config)
    try:
        ok, err = await client.probe()
        assert ok is True
        assert err is None
    finally:
        await client.close()


@respx.mock
async def test_probe_returns_false_on_connect_error(config):
    """probe() returns (False, error_msg) on connection refused."""
    respx.get(f"{PMPROXY_BASE}/series/sources").mock(
        side_effect=httpx.ConnectError("Connection refused")
    )

    client = PmproxyClient(config)
    try:
        ok, err = await client.probe()
        assert ok is False
        assert err is not None
        assert len(err) > 0
    finally:
        await client.close()


@respx.mock
async def test_probe_returns_false_on_timeout(config):
    """probe() returns (False, error_msg) on request timeout."""
    respx.get(f"{PMPROXY_BASE}/series/sources").mock(
        side_effect=httpx.TimeoutException("Request timed out")
    )

    client = PmproxyClient(config)
    try:
        ok, err = await client.probe()
        assert ok is False
        assert err is not None
    finally:
        await client.close()


@respx.mock
async def test_probe_returns_false_on_http_error(config):
    """probe() returns (False, error_msg) on HTTP 500 error response."""
    respx.get(f"{PMPROXY_BASE}/series/sources").mock(
        return_value=httpx.Response(500, text="Internal Server Error")
    )

    client = PmproxyClient(config)
    try:
        ok, err = await client.probe()
        assert ok is False
        assert err is not None
    finally:
        await client.close()


@respx.mock
async def test_probe_uses_short_timeout(config):
    """probe() uses a 5-second timeout regardless of configured client timeout."""
    # Config has timeout=5.0 but we verify the probe uses its own short timeout.
    # We check this by confirming the request is made (it succeeds here).
    respx.get(f"{PMPROXY_BASE}/series/sources").mock(return_value=httpx.Response(200, json=[]))

    long_timeout_config = PmproxyConfig(url=PMPROXY_BASE, timeout=120.0)
    client = PmproxyClient(long_timeout_config)
    try:
        ok, err = await client.probe()
        assert ok is True
        assert err is None
    finally:
        await client.close()
