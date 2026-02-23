# Data Model: PCP MCP Service (pmmcp)

**Feature**: 001-pcp-mcp-service
**Date**: 2026-02-21

## Overview

pmmcp is a stateless MCP server — it does not own or persist data. All data originates from pmproxy and flows through pmmcp to the AI agent. This document defines the Pydantic models that represent pmproxy data as it moves through the system.

All models use Pydantic v2 for runtime validation and automatic JSON schema generation.

## Core Models

### PmproxyConfig

Connection configuration for the pmproxy endpoint.

```python
class PmproxyConfig(BaseModel):
    url: str              # Full base URL (e.g., "http://localhost:44322")
    timeout: float = 30.0 # Request timeout in seconds
```

Design note: Fields for `username` and `password` are intentionally omitted from the initial build but the model is structured as an object (not a flat URL string) to accommodate future credential fields without breaking changes.

### Host

A monitored machine visible to pmproxy.

```python
class Host(BaseModel):
    source: str                        # Series source identifier (hash)
    hostnames: list[str]               # One or more hostnames/addresses
    labels: dict[str, str] = {}        # Host-level labels (platform, domain, etc.)
```

Sourced from: `/series/sources`, `/pmapi/context`

### Metric

A named performance measurement.

```python
class Metric(BaseModel):
    name: str                          # Fully qualified name (e.g., "kernel.percpu.cpu.user")
    pmid: str                          # PCP metric identifier
    type: str                          # Value type: "32", "u32", "64", "u64", "float", "double", "string"
    semantics: str                     # "instant", "counter", or "discrete"
    units: str                         # Human-readable units (e.g., "millisec", "Kbyte", "count / sec")
    indom: str | None = None           # Instance domain identifier, None if singular
    series: str = ""                   # Time-series identifier (hash)
    source: str = ""                   # Source (host) identifier
    labels: dict[str, str] = {}        # Metric-level labels
    oneline: str = ""                  # One-line description
    helptext: str = ""                 # Full help text
```

Sourced from: `/pmapi/metric`, `/series/descs`, `/series/labels`

### Instance

A member of an instance domain (e.g., a specific CPU, disk, or network interface).

```python
class Instance(BaseModel):
    instance: int                      # Instance identifier (numeric)
    name: str                          # Instance name (e.g., "cpu0", "sda", "eth0")
    series: str = ""                   # Series identifier for this instance
    source: str = ""                   # Source (host) identifier
    labels: dict[str, str] = {}        # Instance-level labels
```

Sourced from: `/pmapi/indom`, `/series/instances`

### MetricValue

A single timestamped data point.

```python
class MetricValue(BaseModel):
    series: str                        # Series identifier
    timestamp: int                     # Nanosecond-precision Unix timestamp
    value: str | float | int           # The sampled value
    instance: str | None = None        # Instance name, if applicable
```

Sourced from: `/pmapi/fetch`, `/series/values`

### TimeWindow

A bounded time range for queries.

```python
class TimeWindow(BaseModel):
    start: str = "-1hour"              # ISO-8601 datetime or PCP relative expression
    end: str = "now"                   # ISO-8601 datetime or "now"
    interval: str = "auto"             # Sampling interval ("15s", "5min", "1hour", "auto")
```

Used by: `pcp_fetch_timeseries`, `pcp_query_series`, `pcp_compare_windows`

### WindowStats

Summary statistics for a single time window.

```python
class WindowStats(BaseModel):
    mean: float
    min: float
    max: float
    p95: float
    stddev: float
    sample_count: int
```

### DeltaStats

Computed differences between two windows.

```python
class DeltaStats(BaseModel):
    mean_change: float                 # Absolute change in mean
    mean_change_pct: float             # Percentage change in mean
    stddev_change: float               # Change in standard deviation
    significant: bool                  # True if |mean_change| > 2 * baseline stddev
```

### WindowComparison

Full comparison result for a metric across two windows.

```python
class WindowComparison(BaseModel):
    metric: str                        # Metric name
    instance: str | None = None        # Instance name, if applicable
    window_a: WindowStats              # Stats for the baseline window
    window_b: WindowStats              # Stats for the comparison window
    delta: DeltaStats                  # Computed differences
```

Used by: `pcp_compare_windows`

### SearchResult

A result from full-text search.

```python
class SearchResult(BaseModel):
    name: str                          # Metric or instance domain name
    type: str                          # "metric", "indom", or "instance"
    oneline: str = ""                  # One-line description
    helptext: str = ""                 # Full help text
    score: float = 0.0                 # Relevance score
```

Sourced from: `/search/text`

### PaginatedResponse

Generic wrapper for paginated tool responses.

```python
class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]                     # Result items for this page
    total: int = -1                    # Total available items (-1 if unknown)
    limit: int                         # Items per page (as requested)
    offset: int                        # Current offset
    has_more: bool                     # True if more pages available
```

Used by: All list-returning tools.

## PmproxyClient Interface

The `PmproxyClient` class (`src/pmmcp/client.py`) is the single point of contact with pmproxy. All tool handlers call client methods; no tool handler makes HTTP requests directly.

### Two API Surfaces

pmproxy exposes two distinct REST API families. The client must handle both:

| Surface | URL prefix | State | Used by |
|---------|-----------|-------|---------|
| **Series API** | `/series/*`, `/search/*` | Stateless — no context needed | `pcp_get_hosts`, `pcp_discover_metrics` (search path), `pcp_fetch_timeseries`, `pcp_query_series`, `pcp_compare_windows`, `pcp_search` |
| **PMAPI** | `/pmapi/*` | Context-based — requires context ID | `pcp_discover_metrics` (tree path), `pcp_get_metric_info`, `pcp_fetch_live`, `pcp_derive_metric` |

### Context Lifecycle (PMAPI only)

PMAPI endpoints require a context created via `GET /pmapi/context?hostspec=...`. Contexts expire after `polltimeout` seconds of inactivity (default: 5s). The client must:

1. Create a context on first PMAPI call for a given host.
2. Cache the context ID and reuse it for subsequent calls to the same host.
3. Set `polltimeout` to a longer value (e.g., 120s) to avoid premature expiry during multi-step tool calls.
4. On HTTP 403/404 with an expired-context error message, discard the cached context and retry once with a fresh context.
5. Not attempt to persist contexts across MCP server restarts — pmmcp is stateless.

### Client Methods

```python
class PmproxyClient:
    """Async HTTP client for pmproxy REST API."""

    def __init__(self, config: PmproxyConfig) -> None:
        """Initialise with connection config. Creates httpx.AsyncClient."""

    async def close(self) -> None:
        """Close the underlying HTTP client."""

    # ── Series API (stateless) ──────────────────────────────────

    async def series_sources(self, match: str = "") -> list[dict]:
        """GET /series/sources — list monitored hosts.
        Returns raw pmproxy response: [{"source": "...", "context": [...]}]"""

    async def series_query(self, expr: str) -> list[str]:
        """GET /series/query?expr=... — resolve expression to series IDs.
        Returns list of 40-char SHA-1 series identifier strings."""

    async def series_values(
        self, series: list[str], start: str, finish: str,
        interval: str | None = None, samples: int | None = None
    ) -> list[dict]:
        """GET /series/values — fetch time-series data points.
        Returns [{"series": "...", "timestamp": float, "value": "..."}]"""

    async def series_descs(self, series: list[str]) -> list[dict]:
        """GET /series/descs — metric descriptors for series IDs.
        Returns [{"series": "...", "pmid": "...", "type": "...", ...}]"""

    async def series_instances(self, series: list[str]) -> list[dict]:
        """GET /series/instances — instance domain members.
        Returns [{"series": "...", "instance": "...", "id": int, "name": "..."}]"""

    async def series_labels(self, series: list[str]) -> list[dict]:
        """GET /series/labels — labels for series.
        Returns [{"series": "...", "labels": {...}}]"""

    # ── Search API (stateless) ──────────────────────────────────

    async def search_text(
        self, query: str, result_type: str = "",
        limit: int = 10, offset: int = 0
    ) -> dict:
        """GET /search/text — full-text search.
        Returns {"total": int, "results": [...], "offset": int, "limit": int}"""

    async def search_suggest(self, query: str, limit: int = 10) -> list[str]:
        """GET /search/suggest — autocomplete.
        Returns flat list of suggestion strings."""

    # ── PMAPI (context-based) ───────────────────────────────────

    async def _ensure_context(self, host: str = "") -> int:
        """Get or create a PMAPI context for the given host.
        Caches context IDs. Retries on expired context."""

    async def pmapi_metric(
        self, names: list[str], host: str = ""
    ) -> dict:
        """GET /pmapi/metric — metric metadata.
        Returns {"context": int, "metrics": [{name, pmid, type, sem, units, ...}]}"""

    async def pmapi_fetch(
        self, names: list[str], host: str = ""
    ) -> dict:
        """GET /pmapi/fetch — live metric values.
        Returns {"context": int, "timestamp": float, "values": [...]}"""

    async def pmapi_indom(
        self, metric_name: str, host: str = ""
    ) -> dict:
        """GET /pmapi/indom — instance domain listing.
        Returns {"context": int, "indom": "...", "instances": [...]}"""

    async def pmapi_children(
        self, prefix: str, host: str = ""
    ) -> dict:
        """GET /pmapi/children — namespace tree traversal.
        Returns {"context": int, "name": "...", "leaf": [...], "nonleaf": [...]}"""

    async def pmapi_derive(
        self, name: str, expr: str, host: str = ""
    ) -> dict:
        """GET /pmapi/derive — register derived metric.
        Returns {"context": int, "success": true}"""
```

### Error Handling in Client

The client translates pmproxy HTTP responses into Python exceptions. Tool handlers catch these and format MCP error responses.

```python
class PmproxyError(Exception):
    """Base exception for pmproxy communication errors."""
    pass

class PmproxyConnectionError(PmproxyError):
    """pmproxy is unreachable (connection refused, DNS failure, timeout)."""
    pass

class PmproxyNotFoundError(PmproxyError):
    """Requested metric, host, or instance does not exist (HTTP 400/404)."""
    pass

class PmproxyTimeoutError(PmproxyError):
    """Request to pmproxy exceeded the configured timeout."""
    pass

class PmproxyAPIError(PmproxyError):
    """pmproxy returned an error response (HTTP 4xx/5xx with error body)."""
    def __init__(self, status_code: int, message: str): ...
```

**HTTP status → exception mapping:**

| pmproxy HTTP status | Error body pattern | Client exception |
|--------------------|--------------------|-----------------|
| Connection refused / DNS error | (no response) | `PmproxyConnectionError` |
| Read timeout | (no response) | `PmproxyTimeoutError` |
| 200 with `"success": false` | `{"message": "..."}` | `PmproxyAPIError` |
| 400 | `{"message": "Bad request..."}` | `PmproxyNotFoundError` (if "Unknown metric") or `PmproxyAPIError` |
| 403 | `{"message": "..."}` | Expired context → retry; else `PmproxyAPIError` |
| 404 | `{"message": "...traversal failed..."}` | `PmproxyNotFoundError` |
| 5xx | varies | `PmproxyAPIError` |

### Auto-Interval Resolution

The `"auto"` interval value is resolved **in `utils.py`** before any call to pmproxy. pmproxy does not understand `"auto"` — it must receive a concrete interval string.

```python
def resolve_interval(start: str, end: str, interval: str) -> str:
    """Resolve 'auto' interval to a concrete value based on window duration.

    See research.md Decision 8 for the mapping table:
      ≤ 1 hour  → "15s"
      ≤ 24 hours → "5min"
      ≤ 7 days  → "1hour"
      > 7 days  → "6hour"

    If interval is not "auto", returns it unchanged.
    Requires parsing start/end into absolute timestamps to compute duration.
    """
```

This function is called by tool handlers in `tools/timeseries.py`, `tools/series.py`, and `tools/compare.py` before passing the interval to `PmproxyClient.series_values()`.

## Model Relationships

```
PmproxyConfig ──connects-to──▶ pmproxy REST API
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
                  Host          Metric          SearchResult
                    │               │
                    │         ┌─────┴─────┐
                    │         ▼           ▼
                    │     Instance   MetricValue
                    │         │           │
                    └─────────┴───────────┘
                              │
                      TimeWindow (scopes queries)
                              │
                    WindowComparison (analysis output)
```

## State Transitions

pmmcp is stateless — no entities have persistent lifecycle. However, pmproxy contexts have transient state:

```
pmproxy context lifecycle:
  Created ──(via /pmapi/context)──▶ Active ──(polltimeout expires)──▶ Expired
```

pmmcp creates contexts on-demand for live queries (PMAPI path) and lets them expire naturally. Time-series queries (series path) are stateless.

## Validation Rules

- `PmproxyConfig.url` MUST be a valid HTTP/HTTPS URL (validated via Pydantic `AnyHttpUrl` or custom validator).
- `Metric.name` MUST be a dot-separated namespace (e.g., `kernel.all.cpu.user`).
- `TimeWindow.start` MUST be before `TimeWindow.end` when both are absolute timestamps.
- `TimeWindow.interval` MUST be one of: a duration string (`Ns`, `Nmin`, `Nhour`) or `"auto"`.
- `PaginatedResponse.limit` MUST be between 1 and 1000 (validated via `Field(ge=1, le=1000)`).
- `PaginatedResponse.offset` MUST be >= 0 (validated via `Field(ge=0)`).
