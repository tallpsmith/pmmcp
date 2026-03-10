# Quickstart: Grafana & mcp-grafana Compose Integration

**Branch**: `012-grafana-compose`

## Prerequisites

- podman + podman-compose installed
- Existing pmmcp compose stack working (`podman compose up -d` passes healthchecks)

## Start the Stack

```bash
podman compose up -d --wait --wait-timeout 120
```

This starts all services including Grafana and mcp-grafana.

## Verify Grafana

1. Open http://localhost:3000 in a browser (no login required — anonymous admin enabled)
2. Navigate to Connections → Data sources
3. Confirm "PCP Valkey" and "PCP Vector" datasources are listed and healthy

Or via API:
```bash
curl -s http://localhost:3000/api/datasources | python3 -m json.tool
```

## Verify mcp-grafana

mcp-grafana runs in SSE mode on port 8000:

```bash
# Check mcp-grafana is responding
curl -s http://localhost:8000/sse
```

## Verify Shared Backend

The PCP datasources in Grafana and pmmcp both target the same pmproxy (`http://pcp:44322`). To confirm:

```bash
# Query a metric via pmproxy directly
curl -s "http://localhost:44322/pmapi/metric?names=kernel.all.load"

# Same metric should be explorable in Grafana via PCP Vector datasource
```

## Teardown

```bash
podman compose down --volumes
```

All Grafana state is ephemeral — dashboards and preferences are destroyed on teardown.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Grafana shows "plugin not found" | PCP plugin failed to download | Check container logs: `podman compose logs grafana` — network issue or wrong ZIP URL |
| PCP datasource unhealthy | pmproxy not ready when Grafana started | Wait and retry — Grafana auto-retries datasource connections |
| mcp-grafana "connection refused" | Grafana not healthy yet | mcp-grafana depends on Grafana healthcheck — check `podman compose ps` |
| Unsigned plugin error | Missing `GF_PLUGINS_ALLOW_LOADING_UNSIGNED_PLUGINS` | Verify the env var lists all PCP plugin IDs |
