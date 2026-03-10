# Data Model: Grafana & mcp-grafana Compose Integration

**Date**: 2026-03-10
**Branch**: `012-grafana-compose`

## Overview

This feature is infrastructure-only — no new application data entities are introduced. The "data model" here describes the compose service topology and configuration relationships.

## Service Topology

```
┌─────────────────────┐     ┌──────────────┐
│  pmlogsynth-generator│────▶│ pmmcp-archives│ (named volume)
└─────────────────────┘     └──────┬───────┘
                                   │
┌──────────────┐            ┌──────▼───────┐
│ redis-stack  │◀───────────│pmlogsynth-   │
│ (6379)       │            │seeder        │
└──────┬───────┘            └──────────────┘
       │
┌──────▼───────┐
│ pcp          │◀─── KEY_SERVERS=redis-stack:6379
│ (44322)      │
└──┬───────┬───┘
   │       │
   │       │   ┌──────────────┐
   │       └──▶│ grafana      │◀── PCP datasource provisioned
   │           │ (3000)       │    via /etc/grafana/provisioning/
   │           └──────┬───────┘
   │                  │
   │           ┌──────▼───────┐
   │           │ mcp-grafana  │◀── GRAFANA_URL=http://grafana:3000
   │           │ (8000/sse)   │    GRAFANA_USERNAME=admin
   │           └──────────────┘    GRAFANA_PASSWORD=admin
   │
┌──▼───────────┐
│ pmmcp        │◀── PMPROXY_URL=http://pcp:44322
│ (8080)       │
└──────────────┘
```

## Configuration Relationships

| Setting | Source | Consumers | Must Match |
|---------|--------|-----------|------------|
| pmproxy URL (`http://pcp:44322`) | `pcp` service | pmmcp, grafana PCP datasource | Yes — single source of truth |
| Redis/Valkey (`redis-stack:6379`) | `redis-stack` service | pcp, pmlogsynth-seeder | Yes |
| Grafana URL (`http://grafana:3000`) | `grafana` service | mcp-grafana | Yes |
| Grafana credentials (`admin/admin`) | Grafana env vars | mcp-grafana env vars | Yes |

## New Files

| File | Purpose |
|------|---------|
| `grafana/provisioning/datasources/pcp.yaml` | Grafana datasource provisioning — auto-configures PCP Valkey + Vector datasources |
