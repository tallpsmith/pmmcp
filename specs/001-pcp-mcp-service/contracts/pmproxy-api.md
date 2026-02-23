# pmproxy REST API Reference (for pmmcp implementors)

**Feature**: 001-pcp-mcp-service
**Date**: 2026-02-21
**Source**: [PMWEBAPI(3)](https://man7.org/linux/man-pages/man3/pmwebapi.3.html), PCP source code

This document captures the actual JSON response shapes returned by pmproxy endpoints that pmmcp calls. It exists so implementors and test authors know the exact wire format without needing to read PCP source code.

## General Notes

- Default port: **44322** (HTTP)
- All responses are JSON with `Access-Control-Allow-Origin: *`
- Series/source identifiers are **40-character SHA-1 hex strings**
- Timestamps are **floating-point seconds since Unix epoch** (with sub-second precision)
- Values in the Series API are **always strings** (even numeric); values in PMAPI `/fetch` are **typed** (number or string)
- An optional `client` parameter is accepted on all endpoints and echoed back for request correlation

## Error Response Format

All error responses follow this shape:

```json
{
  "context": 703457480,
  "message": "abc traversal failed - Unknown metric name",
  "success": false
}
```

- `context` (number): Present when a PMAPI context exists; absent on series/search endpoints
- `message` (string): Human-readable PMAPI error string
- `success` (boolean): Always `false` on error

**HTTP status codes:**
| Code | Meaning | When |
|------|---------|------|
| 200 | Success | Normal response |
| 400 | Bad request | Invalid parameters, unknown metric name |
| 403 | Forbidden | Expired or invalid context |
| 404 | Not found | Unknown namespace traversal path |
| 409 | Conflict | Duplicate derived metric name |

---

## Series API (`/series/*`) — Stateless

### GET /series/sources

List monitored hosts/archive sources.

**Parameters:** `match` (glob pattern), `series` (comma-separated source hashes)

**Response:**
```json
[
  {
    "source": "2cd6a38f9339f2dd1f0b4775bda89a9e7244def6",
    "context": ["/var/log/pcp/pmlogger/acme", "www.acme.com"]
  }
]
```

| Field | Type | Notes |
|-------|------|-------|
| `source` | string | 40-char SHA-1 source identifier |
| `context` | string[] | Hostnames and/or archive paths |

**pmmcp mapping:** `pcp_get_hosts` → parses `context` array to extract hostnames into `Host.hostnames`. Then calls `/series/labels` with the source hash to populate `Host.labels`.

---

### GET /series/query

Resolve a pmseries expression to series identifiers, optionally with values.

**Parameters:** `expr` (required)

**Response (without time window in expression):** flat array of series ID strings:
```json
["9d8c7fb51ce160eb82e3669aac74ba675dfa8900"]
```

**Response (with time window in expression):** array of value objects:
```json
[
  {
    "series": "9d8c7fb51ce160eb82e3669aac74ba675dfa8900",
    "instance": "c3795d8b757506a2901c6b08b489ba56cae7f0d4",
    "timestamp": 1547483646.2147431,
    "value": "12499"
  }
]
```

**pmmcp mapping:** `pcp_fetch_timeseries` and `pcp_query_series` use the ID-only form to resolve series, then call `/series/values` separately. `pcp_compare_windows` does the same for both windows.

---

### GET /series/values

Fetch time-series data points for known series IDs.

**Parameters:** `series` (comma-separated, required), `start`, `finish`, `interval`, `samples`, `offset`, `zone`, `align`

**Response:**
```json
[
  {
    "series": "605fc77742cd0317597291329561ac4e50c0dd12",
    "timestamp": 1317633022959.959241,
    "value": "71660"
  }
]
```

| Field | Type | Notes |
|-------|------|-------|
| `series` | string | SHA-1 series identifier |
| `timestamp` | number | Float seconds since epoch (high precision) |
| `value` | string | **Always a string** — must be parsed to numeric by pmmcp |

**Important:** No built-in pagination (`offset`/`limit`) for this endpoint. pmmcp enforces its own pagination by requesting data in bounded time windows using `start`/`finish` and `samples`.

---

### GET /series/descs

Metric descriptors for series IDs.

**Parameters:** `series` (comma-separated, required)

**Response:**
```json
[
  {
    "series": "605fc77742cd0317597291329561ac4e50c0dd12",
    "source": "f5ca7481da8c038325d15612bb1c6473ce1ef16f",
    "pmid": "60.0.4",
    "indom": "60.1",
    "semantics": "counter",
    "type": "u32",
    "units": "count"
  }
]
```

| Field | Type | Notes |
|-------|------|-------|
| `series` | string | SHA-1 series ID |
| `source` | string | SHA-1 source ID |
| `pmid` | string | Dotted `domain.cluster.item` |
| `indom` | string | `"domain.serial"` or `"none"` for singular metrics |
| `semantics` | string | `"counter"`, `"instant"`, or `"discrete"` |
| `type` | string | `"32"`, `"u32"`, `"64"`, `"u64"`, `"float"`, `"double"`, `"string"`, `"aggregate"`, `"event"` |
| `units` | string | e.g., `"count"`, `"Kbyte"`, `"millisec / count"`, `"none"` |

---

### GET /series/instances

Instance domain members for series IDs.

**Parameters:** `series` (comma-separated), `match` (glob pattern for instance names)

**Response:**
```json
[
  {
    "series": "605fc77742cd0317597291329561ac4e50c0dd12",
    "source": "97261ac7742cd4e50c0d03175913295d12605fc7",
    "instance": "c3795d8b757506a2901c6b08b489ba56cae7f0d4",
    "id": 1,
    "name": "sda"
  }
]
```

| Field | Type | Notes |
|-------|------|-------|
| `instance` | string | SHA-1 instance identifier |
| `id` | number | Numeric internal instance ID |
| `name` | string | Human-readable instance name (e.g., `"cpu0"`, `"sda"`) |

---

### GET /series/labels

Labels for series IDs.

**Parameters:** `series` (comma-separated)

**Response:**
```json
[
  {
    "series": "605fc77742cd0317597291329561ac4e50c0dd12",
    "labels": {
      "agent": "linux",
      "hostname": "www.acme.com"
    }
  }
]
```

---

## PMAPI (`/pmapi/*`) — Context-Based

### Context Lifecycle

1. Create context via `GET /pmapi/context?hostspec=...&polltimeout=120`
2. Use returned `context` integer in subsequent calls
3. Context expires after `polltimeout` seconds of inactivity
4. On expiry, pmproxy returns HTTP 403 — create a new context and retry
5. All `/pmapi/*` endpoints also accept `hostspec` directly (creates implicit context)

### GET /pmapi/context

**Parameters:** `hostspec` (required), `polltimeout` (default: 5)

**Response:**
```json
{
  "context": 348734,
  "source": "05af7f3eb840277fd3cfa91f90ef0067199743c",
  "hostspec": "www.acme.com",
  "labels": {
    "domainname": "acme.com",
    "hostname": "www.acme.com",
    "platform": "dev"
  }
}
```

---

### GET /pmapi/metric

**Parameters:** `names` (comma-separated), `prefix` (namespace subtree), `context` or `hostspec`

**Response:**
```json
{
  "context": 348734,
  "metrics": [
    {
      "name": "kernel.all.load",
      "pmid": "60.2.0",
      "indom": "60.2",
      "type": "FLOAT",
      "sem": "instant",
      "units": "none",
      "series": "d2b28c7f6dc0d69ffd21dba7ba955e78c37719b",
      "source": "05af7f3eb840277fd3cfa91f90ef0067199743c",
      "labels": {"agent": "linux", "hostname": "www.acme.com"},
      "text-oneline": "1, 5 and 15 minute load average",
      "text-help": "Extended help text..."
    }
  ]
}
```

**Field mapping to pmmcp `Metric` model:**

| pmproxy field | Metric field | Notes |
|---------------|-------------|-------|
| `name` | `name` | Direct |
| `pmid` | `pmid` | Direct |
| `type` | `type` | pmproxy returns uppercase (`"FLOAT"`); normalise to lowercase |
| `sem` | `semantics` | Direct (`"instant"`, `"counter"`, `"discrete"`) |
| `units` | `units` | Direct |
| `indom` | `indom` | `"none"` → `None` |
| `series` | `series` | Direct |
| `source` | `source` | Direct |
| `labels` | `labels` | Direct (values may be string, int, or bool — coerce to string) |
| `text-oneline` | `oneline` | Note the hyphenated key name |
| `text-help` | `helptext` | Note the hyphenated key name; may be absent |

---

### GET /pmapi/fetch

**Parameters:** `names` (comma-separated), `context` or `hostspec`

**Response:**
```json
{
  "context": 348734,
  "timestamp": 1547483646.2147431,
  "values": [
    {
      "pmid": "60.2.0",
      "name": "kernel.all.load",
      "instances": [
        {"instance": 1, "value": 0.1},
        {"instance": 5, "value": 0.25},
        {"instance": 15, "value": 0.17}
      ]
    }
  ]
}
```

| Field | Type | Notes |
|-------|------|-------|
| `timestamp` | number | Float seconds since epoch |
| `values[].instances[].instance` | number or null | `null` for singular metrics (no instance domain) |
| `values[].instances[].value` | number or string | Typed — numeric for numeric metrics, string for STRING type |

**pmmcp mapping:** Tool handler must join `instance` IDs with instance names from `/pmapi/indom` to produce human-readable output.

---

### GET /pmapi/indom

**Parameters:** `name` (metric name) or `indom` (domain ID), `context` or `hostspec`

**Response:**
```json
{
  "context": 348734,
  "indom": "60.2",
  "labels": {"hostname": "www.acme.com"},
  "instances": [
    {"instance": 1, "name": "1 minute", "labels": {}},
    {"instance": 5, "name": "5 minute", "labels": {}},
    {"instance": 15, "name": "15 minute", "labels": {}}
  ]
}
```

---

### GET /pmapi/children

**Parameters:** `prefix` (required), `context` or `hostspec`

**Response:**
```json
{
  "context": 348734,
  "name": "mem",
  "leaf": ["physmem", "freemem"],
  "nonleaf": ["util", "numa", "vmstat"]
}
```

| Field | Type | Notes |
|-------|------|-------|
| `leaf` | string[] | Children that are actual metrics (fetchable) |
| `nonleaf` | string[] | Children that are subtrees (traversable) |

**pmmcp mapping:** `pcp_discover_metrics` (tree-browse path). Returns combined list with `leaf: bool` flag for each child.

---

### GET /pmapi/derive

**Parameters:** `name` (required), `expr` (required), `context` or `hostspec`

**Response:**
```json
{"context": 348734, "success": true}
```

**On error** (e.g., invalid expression):
```json
{"context": 348734, "message": "Semantic error...", "success": false}
```

---

## Search API (`/search/*`)

Requires pmproxy configured with Valkey/Redis + RediSearch module.

### GET /search/text

**Parameters:** `query` (required), `type` (`"metric"`, `"indom"`, `"instance"`), `limit` (default: 10), `offset` (default: 0)

**Response:**
```json
{
  "total": 42,
  "elapsed": 0.0042,
  "offset": 0,
  "limit": 10,
  "results": [
    {
      "name": "kernel.all.load",
      "type": "metric",
      "oneline": "1, 5 and 15 minute load average",
      "helptext": "Extended help text..."
    }
  ]
}
```

**pmmcp mapping to `SearchResult`:** `name` → `name`, `type` → `type`, `oneline` → `oneline`, `helptext` → `helptext`. The `score` field in `SearchResult` is not provided by pmproxy — set to `0.0` or derive from result position.

**pmmcp mapping to `PaginatedResponse`:** `total` → `total`, `offset` → `offset`, `limit` → `limit`, `has_more` = `offset + limit < total`.

---

### GET /search/suggest

**Parameters:** `query` (required), `limit`

**Response:** flat array of strings:
```json
["kernel.all.load", "kernel.all.cpu.user", "kernel.percpu.cpu.idle"]
```

---

## Test Fixture Guidance

When building `conftest.py` fixtures, mock pmproxy at the HTTP level using `respx`. Each fixture should return the raw JSON shapes documented above. Key fixtures needed:

| Fixture | Mocks | Used by tests for |
|---------|-------|-------------------|
| `mock_series_sources` | `GET /series/sources` | `pcp_get_hosts` |
| `mock_series_query` | `GET /series/query` | `pcp_fetch_timeseries`, `pcp_query_series`, `pcp_compare_windows` |
| `mock_series_values` | `GET /series/values` | `pcp_fetch_timeseries`, `pcp_query_series`, `pcp_compare_windows` |
| `mock_series_descs` | `GET /series/descs` | `pcp_fetch_timeseries`, `pcp_get_metric_info` (series path) |
| `mock_series_instances` | `GET /series/instances` | `pcp_fetch_timeseries` |
| `mock_series_labels` | `GET /series/labels` | `pcp_get_hosts`, `pcp_fetch_timeseries` |
| `mock_pmapi_context` | `GET /pmapi/context` | all PMAPI tool tests |
| `mock_pmapi_metric` | `GET /pmapi/metric` | `pcp_get_metric_info` |
| `mock_pmapi_fetch` | `GET /pmapi/fetch` | `pcp_fetch_live` |
| `mock_pmapi_indom` | `GET /pmapi/indom` | `pcp_get_metric_info`, `pcp_fetch_live` |
| `mock_pmapi_children` | `GET /pmapi/children` | `pcp_discover_metrics` |
| `mock_pmapi_derive` | `GET /pmapi/derive` | `pcp_derive_metric` |
| `mock_search_text` | `GET /search/text` | `pcp_search`, `pcp_discover_metrics` |
| `mock_search_suggest` | `GET /search/suggest` | `pcp_discover_metrics` |
| `mock_pmproxy_error` | Any endpoint → HTTP 400/404 | Error handling tests |
| `mock_pmproxy_unreachable` | Connection refused | Connection error tests |
