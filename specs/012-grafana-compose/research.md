# Research: Grafana & mcp-grafana Compose Integration

**Date**: 2026-03-10
**Branch**: `012-grafana-compose`

## R1: mcp-grafana Container Image & Transport

**Decision**: Use `mcp/grafana` image from Docker Hub in SSE mode (port 8000, path `/sse`).

**Rationale**: The Docker image defaults to SSE transport, which is the natural fit for a compose service (unlike stdio which requires a parent process). SSE on port 8000 is the documented default.

**Alternatives considered**:
- `stdio` transport — requires wrapping in a parent process, not suitable for compose service
- `streamable-http` — newer, production-oriented, but SSE is simpler and sufficient for dev/test
- Build from source — unnecessary, official image is available and maintained

## R2: mcp-grafana Authentication

**Decision**: Use basic auth (`GRAFANA_USERNAME=admin`, `GRAFANA_PASSWORD=admin`) for the dev/test compose stack.

**Rationale**: mcp-grafana does **not** support anonymous access — it always requires one of: service account token, legacy API key, or basic auth. Basic auth with Grafana's default `admin/admin` is the simplest approach for a dev stack. No init container or API call needed to bootstrap a service account token.

**Alternatives considered**:
- Service account token (`GRAFANA_SERVICE_ACCOUNT_TOKEN`) — requires creating the token after Grafana starts (init container or API call), adds complexity for no dev/test benefit
- Legacy API key (`GRAFANA_API_KEY`) — deprecated by Grafana, not recommended
- Anonymous admin with no auth — not supported by mcp-grafana

**mcp-grafana environment variables**:
- `GRAFANA_URL` — Grafana instance URL (e.g., `http://grafana:3000`)
- `GRAFANA_USERNAME` — basic auth username
- `GRAFANA_PASSWORD` — basic auth password

## R3: PCP Grafana Plugin Installation

**Decision**: Install `performancecopilot-pcp-app` via `GF_INSTALL_PLUGINS` with direct ZIP URL from GitHub releases. Allow unsigned plugins via `GF_PLUGINS_ALLOW_LOADING_UNSIGNED_PLUGINS`.

**Rationale**: The plugin is unsigned (community-maintained), so it's not available via the standard Grafana plugin catalog shorthand. The GitHub releases ZIP URL is the documented installation method.

**Alternatives considered**:
- Custom Grafana image with plugin pre-installed — adds a build step and image maintenance burden
- Grafana plugin catalog shorthand — doesn't work for unsigned plugins

**Configuration**:
```
GF_INSTALL_PLUGINS=https://github.com/performancecopilot/grafana-pcp/releases/download/v5.3.0/performancecopilot-pcp-app-5.3.0.zip;performancecopilot-pcp-app
GF_PLUGINS_ALLOW_LOADING_UNSIGNED_PLUGINS=performancecopilot-pcp-app,performancecopilot-valkey-datasource,performancecopilot-vector-datasource,performancecopilot-bpftrace-datasource,performancecopilot-flamegraph-panel,performancecopilot-breadcrumbs-panel,performancecopilot-troubleshooting-panel
```

## R4: PCP Datasource Types & Provisioning

**Decision**: Provision two datasources — `performancecopilot-valkey-datasource` (historical/timeseries) and `performancecopilot-vector-datasource` (live metrics). Both point at `http://pcp:44322`.

**Rationale**: The Valkey datasource uses pmproxy's `/series/*` endpoints (backed by Redis/Valkey — already in our compose stack). The Vector datasource uses `/pmapi/*` for live metrics. Both are useful for the Issue #10 visualisation workflows.

**Alternatives considered**:
- Valkey datasource only — misses live metric visualisation
- bpftrace datasource — requires bpftrace PMDA, out of scope

**Provisioning YAML** (`grafana/provisioning/datasources/pcp.yaml`):
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

## R5: Grafana Version & Configuration

**Decision**: Use `grafana/grafana:latest` with anonymous auth enabled for browser access, plus basic auth credentials for mcp-grafana API access.

**Rationale**: Plugin requires Grafana >=9.0.9. Using `latest` keeps us current. Anonymous auth for browser means no login prompt for developers, while mcp-grafana uses basic auth for API calls. Grafana supports both simultaneously.

**Alternatives considered**:
- Pin specific version (e.g., `grafana/grafana:11.x`) — better for reproducibility but adds maintenance; can pin later if instability appears
- Disable anonymous auth — forces login, friction for dev workflow

**Grafana env vars**:
```
GF_AUTH_ANONYMOUS_ENABLED=true
GF_AUTH_ANONYMOUS_ORG_ROLE=Admin
GF_SECURITY_ADMIN_USER=admin
GF_SECURITY_ADMIN_PASSWORD=admin
```

## R6: CI Parity Approach

**Decision**: Add Grafana and mcp-grafana to the CI E2E job using the same `docker compose up -d` approach already used for pcp/redis. No separate service containers needed.

**Rationale**: The CI workflow already uses `docker compose up -d --wait` to start the full compose stack. Adding Grafana and mcp-grafana to `docker-compose.yml` means CI automatically picks them up. This maintains the parity convention.

**Alternatives considered**:
- GitHub Actions service containers — would diverge from compose topology, exactly the anti-pattern documented in CLAUDE.md
- Separate Grafana compose file — unnecessary fragmentation

**CI changes**: Minimal — add a "Wait for Grafana" step after "Wait for pmproxy" to confirm Grafana is healthy before E2E tests run. Also set `GRAFANA_URL=http://localhost:3000` env var for any Grafana-specific E2E tests.
