"""Tests for PmproxyClient._post method."""

from __future__ import annotations

import httpx
import pytest
import respx

from pmmcp.client import PmproxyClient, PmproxyConnectionError, PmproxyTimeoutError
from pmmcp.config import PmproxyConfig

PMPROXY_BASE = "http://localhost:44322"


@pytest.fixture
def config():
    return PmproxyConfig(url=PMPROXY_BASE, timeout=5.0)


@respx.mock
async def test_post_sends_form_encoded_body(config):
    """_post sends data as application/x-www-form-urlencoded."""
    route = respx.post(f"{PMPROXY_BASE}/series/values").mock(
        return_value=httpx.Response(200, json=[{"series": "abc", "value": "1"}])
    )

    client = PmproxyClient(config)
    try:
        response = await client._post(
            "/series/values", data={"series": "abc,def", "start": "-1hours"}
        )
        assert response.status_code == 200

        # Verify form-encoded content type was sent
        request = route.calls[0].request
        content_type = request.headers.get("content-type", "")
        assert "application/x-www-form-urlencoded" in content_type
    finally:
        await client.close()


@respx.mock
async def test_post_wraps_connect_error(config):
    """_post wraps httpx.ConnectError as PmproxyConnectionError."""
    respx.post(f"{PMPROXY_BASE}/series/values").mock(
        side_effect=httpx.ConnectError("Connection refused")
    )

    client = PmproxyClient(config)
    try:
        with pytest.raises(PmproxyConnectionError):
            await client._post("/series/values", data={"series": "abc"})
    finally:
        await client.close()


@respx.mock
async def test_post_wraps_remote_protocol_error(config):
    """_post wraps httpx.RemoteProtocolError as PmproxyConnectionError."""
    respx.post(f"{PMPROXY_BASE}/series/values").mock(
        side_effect=httpx.RemoteProtocolError("Content-Length mismatch")
    )

    client = PmproxyClient(config)
    try:
        with pytest.raises(PmproxyConnectionError):
            await client._post("/series/values", data={"series": "abc"})
    finally:
        await client.close()


@respx.mock
async def test_post_wraps_timeout_exception(config):
    """_post wraps httpx.TimeoutException as PmproxyTimeoutError."""
    respx.post(f"{PMPROXY_BASE}/series/values").mock(
        side_effect=httpx.TimeoutException("Request timed out")
    )

    client = PmproxyClient(config)
    try:
        with pytest.raises(PmproxyTimeoutError):
            await client._post("/series/values", data={"series": "abc"})
    finally:
        await client.close()


@respx.mock
async def test_post_calls_raise_for_response(config):
    """_post delegates error responses to _raise_for_response."""
    respx.post(f"{PMPROXY_BASE}/series/values").mock(
        return_value=httpx.Response(404, json={"message": "not found"})
    )

    client = PmproxyClient(config)
    try:
        from pmmcp.client import PmproxyNotFoundError

        with pytest.raises(PmproxyNotFoundError):
            await client._post("/series/values", data={"series": "abc"})
    finally:
        await client.close()
