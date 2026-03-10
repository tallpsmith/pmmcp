# Compose Service Contracts: Grafana Integration

**Date**: 2026-03-10

## New Services

### grafana

| Property | Value |
|----------|-------|
| Image | `grafana/grafana:latest` |
| Port | `3000:3000` |
| Depends on | `pcp` (service_started) |
| Healthcheck | `curl -sf http://localhost:3000/api/health` |
| Volumes | `./grafana/provisioning:/etc/grafana/provisioning:ro` |

**Environment**:
```
GF_INSTALL_PLUGINS=https://github.com/performancecopilot/grafana-pcp/releases/download/v5.3.0/performancecopilot-pcp-app-5.3.0.zip;performancecopilot-pcp-app
GF_PLUGINS_ALLOW_LOADING_UNSIGNED_PLUGINS=performancecopilot-pcp-app,performancecopilot-valkey-datasource,performancecopilot-vector-datasource,performancecopilot-bpftrace-datasource,performancecopilot-flamegraph-panel,performancecopilot-breadcrumbs-panel,performancecopilot-troubleshooting-panel
GF_AUTH_ANONYMOUS_ENABLED=true
GF_AUTH_ANONYMOUS_ORG_ROLE=Admin
GF_SECURITY_ADMIN_USER=admin
GF_SECURITY_ADMIN_PASSWORD=admin
```

### mcp-grafana

| Property | Value |
|----------|-------|
| Image | `mcp/grafana` |
| Port | `8000:8000` |
| Depends on | `grafana` (service_healthy) |
| Transport | SSE (default for Docker image) |
| Endpoint | `/sse` on port 8000 |

**Environment**:
```
GRAFANA_URL=http://grafana:3000
GRAFANA_USERNAME=admin
GRAFANA_PASSWORD=admin
```

## Provisioned Datasources

File: `grafana/provisioning/datasources/pcp.yaml`

```yaml
apiVersion: 1
datasources:
  - name: PCP Valkey
    type: performancecopilot-valkey-datasource
    access: proxy
    url: http://pcp:44322
    isDefault: true
    editable: true

  - name: PCP Vector
    type: performancecopilot-vector-datasource
    access: proxy
    url: http://pcp:44322
    editable: true
```

## Service Dependency Chain

```
redis-stack (healthy)
    ↓
pmlogsynth-generator (completed) → pmlogsynth-seeder (completed)
    ↓
pcp (started)
    ↓
├── pmmcp (started)
└── grafana (healthy)
        ↓
    mcp-grafana (started)
```
