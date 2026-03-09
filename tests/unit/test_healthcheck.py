"""Tests for /healthcheck custom route."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

from pmmcp import __version__

PMPROXY_URL = "http://localhost:44322"


def _make_mock_client(probe_result: tuple[bool, str | None]):
    """Build a mock PmproxyClient with a fixed probe() return value."""
    client = MagicMock()
    client._config.url = PMPROXY_URL
    client.probe = AsyncMock(return_value=probe_result)
    return client


async def test_healthcheck_200_when_probe_succeeds():
    """Returns 200 with status=ok and all expected fields when probe passes."""
    from pmmcp.server import _healthcheck_impl

    client = _make_mock_client((True, None))
    response = await _healthcheck_impl(client)

    assert response.status_code == 200
    data = json.loads(response.body)
    assert data["status"] == "ok"
    assert data["connection_ok"] is True
    assert data["pmproxy_url"] == PMPROXY_URL
    assert data["pmmcp_version"] == __version__
    assert "probe_latency_ms" in data
    assert isinstance(data["probe_latency_ms"], (int, float))


async def test_healthcheck_503_when_probe_fails():
    """Returns 503 with status=error and error field when probe fails."""
    from pmmcp.server import _healthcheck_impl

    client = _make_mock_client((False, "Connection refused"))
    response = await _healthcheck_impl(client)

    assert response.status_code == 503
    data = json.loads(response.body)
    assert data["status"] == "error"
    assert data["connection_ok"] is False
    assert data["error"] == "Connection refused"
    assert data["pmproxy_url"] == PMPROXY_URL
    assert data["pmmcp_version"] == __version__
    assert "probe_latency_ms" not in data


async def test_healthcheck_latency_is_non_negative():
    """probe_latency_ms is a non-negative number."""
    from pmmcp.server import _healthcheck_impl

    client = _make_mock_client((True, None))
    response = await _healthcheck_impl(client)

    data = json.loads(response.body)
    assert data["probe_latency_ms"] >= 0


async def test_healthcheck_error_message_propagated():
    """Error string from probe() is passed through to the response body."""
    from pmmcp.server import _healthcheck_impl

    client = _make_mock_client((False, "timed out after 5s"))
    response = await _healthcheck_impl(client)

    data = json.loads(response.body)
    assert data["error"] == "timed out after 5s"


async def test_healthcheck_returns_starting_when_client_is_none():
    """Before any MCP session connects (HTTP mode), healthcheck returns 503 starting."""
    import pmmcp.server as srv

    # Temporarily set _client to None (simulates pre-session state)
    original = srv._client
    srv._client = None
    try:
        from starlette.requests import Request

        response = await srv.healthcheck(Request(scope={"type": "http"}))
        assert response.status_code == 503
        data = json.loads(response.body)
        assert data["status"] == "starting"
        assert data["pmmcp_version"] == __version__
    finally:
        srv._client = original
