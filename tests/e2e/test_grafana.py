"""E2E tests for Grafana and mcp-grafana compose services.

Requires: GRAFANA_URL set and a running Grafana + PCP stack.
Gating: tests skip when GRAFANA_URL is not set.

Run locally:
  podman compose up -d --wait
  PMPROXY_URL=http://localhost:44322 GRAFANA_URL=http://localhost:3000 \
    uv run pytest tests/e2e/test_grafana.py -m e2e
"""

from __future__ import annotations

import os

import httpx
import pytest

GRAFANA_URL = os.environ.get("GRAFANA_URL")

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(not GRAFANA_URL, reason="GRAFANA_URL not set"),
]


# ---------------------------------------------------------------------------
# US1: Grafana with PCP datasources
# ---------------------------------------------------------------------------


def test_grafana_health():
    """T003 — Grafana is accessible and healthy."""
    resp = httpx.get(f"{GRAFANA_URL}/api/health", timeout=10)
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("database") == "ok"


def test_pcp_datasources_provisioned():
    """T004 — PCP Valkey and PCP Vector datasources are provisioned."""
    resp = httpx.get(f"{GRAFANA_URL}/api/datasources", timeout=10)
    assert resp.status_code == 200
    datasources = resp.json()
    names = {ds["name"] for ds in datasources}
    assert "PCP Valkey" in names, f"Missing PCP Valkey; got {names}"
    assert "PCP Vector" in names, f"Missing PCP Vector; got {names}"


def test_pcp_valkey_datasource_healthy():
    """T005 — PCP Valkey datasource can reach pmproxy."""
    # First get the datasource ID
    resp = httpx.get(f"{GRAFANA_URL}/api/datasources", timeout=10)
    assert resp.status_code == 200
    datasources = resp.json()
    valkey_ds = next((ds for ds in datasources if ds["name"] == "PCP Valkey"), None)
    assert valkey_ds is not None, "PCP Valkey datasource not found"

    # Health check via datasource proxy — tests pmproxy connectivity
    ds_id = valkey_ds["id"]
    health_resp = httpx.get(
        f"{GRAFANA_URL}/api/datasources/{ds_id}/health",
        timeout=15,
    )
    # 200 = healthy, but even a non-500 confirms Grafana can talk to the datasource
    assert health_resp.status_code == 200, (
        f"Datasource health check failed: {health_resp.status_code} {health_resp.text}"
    )


# ---------------------------------------------------------------------------
# US2: mcp-grafana SSE endpoint
# ---------------------------------------------------------------------------

MCP_GRAFANA_URL = os.environ.get("MCP_GRAFANA_URL", "http://localhost:8000")


@pytest.mark.skipif(
    not os.environ.get("MCP_GRAFANA_URL") and not GRAFANA_URL,
    reason="MCP_GRAFANA_URL not set",
)
def test_mcp_grafana_sse_responds():
    """T008 — mcp-grafana SSE endpoint accepts connections."""
    # SSE endpoint should return a streaming response; we just verify it connects
    with httpx.stream("GET", f"{MCP_GRAFANA_URL}/sse", timeout=10) as resp:
        assert resp.status_code == 200
        content_type = resp.headers.get("content-type", "")
        assert "text/event-stream" in content_type, (
            f"Expected text/event-stream, got {content_type}"
        )
