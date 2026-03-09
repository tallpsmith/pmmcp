"""Integration test: pmmcp starts in HTTP mode and exposes /healthcheck."""

from __future__ import annotations

import subprocess
import time

import httpx
import pytest


@pytest.mark.integration
def test_http_transport_healthcheck():
    """pmmcp --transport streamable-http starts and /healthcheck responds.

    No MCP session connects, so the healthcheck returns 200 "starting"
    (HTTP transport is up and ready).  We're testing that the HTTP server
    boots and responds, not that pmproxy is actually there.
    """
    proc = subprocess.Popen(
        [
            "uv",
            "run",
            "python",
            "-m",
            "pmmcp",
            "--transport",
            "streamable-http",
            "--port",
            "18080",
            "--pmproxy-url",
            "http://localhost:59999",
        ],
        stderr=subprocess.PIPE,
    )
    try:
        # Give the server a moment to bind
        time.sleep(2)
        assert proc.poll() is None, f"Process exited early: {proc.stderr.read().decode()}"

        resp = httpx.get("http://127.0.0.1:18080/healthcheck", timeout=5)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "starting"
        assert "pmmcp_version" in body
    finally:
        proc.terminate()
        proc.wait(timeout=5)
