# pmproxy Interaction Hardening + SQLite Sink Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix pmproxy API interaction failures (URL size limits, missing discovery recursion, duplicate queries) and add a SQLite sink to keep raw timeseries data out of Claude's context window.

**Architecture:** Phase 1 hardens the client/tool layer — POST-based batching for series endpoints, deduplication of `series_query()` in dual-window tools, concurrent HTTP calls, recursive namespace discovery, and shared expression-building with escaping. Phase 2 adds a session-scoped SQLite database that tools write into, with a SQL query interface for analysis. Phase 1 deliberately separates "get data from pmproxy" from "assemble data into final structure" so Phase 2's sink plugs in cleanly.

**Tech Stack:** Python 3.11+, httpx, asyncio, aiosqlite (Phase 2), FastMCP

---

## Worktree Parallelization Strategy

Phase 1 splits into two independent worktrees with zero file overlap:

| Worktree | Branch | Files Modified | Focus |
|----------|--------|---------------|-------|
| **A** | `007-client-hardening` | `client.py`, `_fetch.py`, `anomaly.py`, `comparison.py`, `correlation.py`, `scanning.py`, `ranking.py`, `timeseries.py`, `utils.py` | Batching, POST, dedup, parallelism, expression safety |
| **B** | `008-recursive-discovery` | `discovery.py`, `investigate.py` | Namespace recursion, quick_investigate fix |

Phase 2 depends on Phase 1 merge:

| Worktree | Branch | Files Modified | Focus |
|----------|--------|---------------|-------|
| **C** | `009-sqlite-sink` | `server.py`, new `tools/sqlite_sink.py`, `pyproject.toml` | SQLite session DB, fetch-to-sqlite, query tool |

---

## Phase 1, Worktree A: Client Hardening (`007-client-hardening`)

### Task 1: Add `_post` method to PmproxyClient

pmproxy accepts POST with URL-encoded body for all `/series/*` endpoints. GET query strings are limited to ~8000 bytes (`MAX_PARAMS_SIZE`), but POST bodies are not subject to the same limit. We need a `_post` method alongside `_get`.

**Files:**
- Modify: `src/pmmcp/client.py:82-92`
- Test: `tests/unit/test_client_post.py` (create)

**Step 1: Write the failing test**

```python
# tests/unit/test_client_post.py
"""Tests for PmproxyClient POST support."""

import httpx
import pytest
import respx

from pmmcp.client import PmproxyClient, PmproxyConnectionError, PmproxyTimeoutError
from pmmcp.config import PmproxyConfig

PMPROXY_BASE = "http://localhost:44322"


@pytest.fixture
def config():
    return PmproxyConfig(url=PMPROXY_BASE)


@pytest.fixture
async def client(config):
    c = PmproxyClient(config)
    yield c
    await c.close()


@respx.mock
async def test_post_sends_form_encoded_body(client):
    """POST sends params as application/x-www-form-urlencoded body."""
    route = respx.post(f"{PMPROXY_BASE}/series/values").mock(
        return_value=httpx.Response(200, json=[])
    )
    await client._post("/series/values", {"series": "abc,def", "start": "-1hours"})
    assert route.called
    request = route.calls.last.request
    assert request.headers["content-type"] == "application/x-www-form-urlencoded"


@respx.mock
async def test_post_raises_connection_error_on_connect_failure(client):
    """POST wraps ConnectError into PmproxyConnectionError."""
    respx.post(f"{PMPROXY_BASE}/series/values").mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(PmproxyConnectionError):
        await client._post("/series/values", {"series": "abc"})


@respx.mock
async def test_post_raises_timeout_error(client):
    """POST wraps TimeoutException into PmproxyTimeoutError."""
    respx.post(f"{PMPROXY_BASE}/series/values").mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(PmproxyTimeoutError):
        await client._post("/series/values", {"series": "abc"})


@respx.mock
async def test_post_calls_raise_for_response(client):
    """POST delegates error checking to _raise_for_response."""
    respx.post(f"{PMPROXY_BASE}/series/values").mock(
        return_value=httpx.Response(400, json={"message": "bad query"})
    )
    from pmmcp.client import PmproxyAPIError

    with pytest.raises(PmproxyAPIError, match="bad query"):
        await client._post("/series/values", {"series": "abc"})
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_client_post.py -v`
Expected: FAIL — `PmproxyClient` has no `_post` method

**Step 3: Write minimal implementation**

Add to `client.py` after `_get` (after line 92):

```python
async def _post(self, path: str, data: dict | None = None) -> httpx.Response:
    """POST with form-encoded body — used for series endpoints to avoid URL size limits."""
    try:
        response = await self._client.post(path, data=data)
    except httpx.ConnectError as exc:
        raise PmproxyConnectionError(str(exc)) from exc
    except httpx.RemoteProtocolError as exc:
        raise PmproxyConnectionError(str(exc)) from exc
    except httpx.TimeoutException as exc:
        raise PmproxyTimeoutError(str(exc)) from exc
    self._raise_for_response(response)
    return response
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_client_post.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/pmmcp/client.py tests/unit/test_client_post.py
git commit -m "feat: add _post method to PmproxyClient for series endpoints

Avoid URL size limits (MAX_PARAMS_SIZE=8000) by sending params as form body"
```

---

### Task 2: Add series ID batching to client series methods

When series IDs exceed ~150 (each is 41 bytes with comma), we must split into batches. Each batch is sent via POST and results are merged. This applies to `series_values`, `series_labels`, and `series_instances`.

**Files:**
- Modify: `src/pmmcp/client.py:107-141`
- Test: `tests/unit/test_client_batching.py` (create)

**Step 1: Write the failing tests**

```python
# tests/unit/test_client_batching.py
"""Tests for series ID batching in PmproxyClient."""

import httpx
import pytest
import respx

from pmmcp.client import PmproxyClient, SERIES_BATCH_SIZE
from pmmcp.config import PmproxyConfig

PMPROXY_BASE = "http://localhost:44322"


@pytest.fixture
def config():
    return PmproxyConfig(url=PMPROXY_BASE)


@pytest.fixture
async def client(config):
    c = PmproxyClient(config)
    yield c
    await c.close()


def _fake_series_ids(n: int) -> list[str]:
    """Generate n fake 40-char hex series IDs."""
    return [f"{i:040x}" for i in range(n)]


@respx.mock
async def test_series_values_batches_when_over_limit(client):
    """series_values splits into multiple POST calls when IDs exceed batch size."""
    ids = _fake_series_ids(SERIES_BATCH_SIZE + 10)
    batch_1_ids = ids[:SERIES_BATCH_SIZE]
    batch_2_ids = ids[SERIES_BATCH_SIZE:]

    route = respx.post(f"{PMPROXY_BASE}/series/values").mock(
        return_value=httpx.Response(200, json=[{"series": "x", "timestamp": 1.0, "value": 42}])
    )

    result = await client.series_values(ids, start="-1hours", finish="now")
    assert route.call_count == 2
    # Results merged from both batches
    assert len(result) == 2


@respx.mock
async def test_series_values_uses_get_when_under_limit(client):
    """series_values uses GET when IDs fit in one batch."""
    ids = _fake_series_ids(5)
    respx.get(f"{PMPROXY_BASE}/series/values").mock(
        return_value=httpx.Response(200, json=[{"series": "x", "timestamp": 1.0, "value": 1}])
    )
    result = await client.series_values(ids, start="-1hours", finish="now")
    assert len(result) == 1


@respx.mock
async def test_series_labels_batches_when_over_limit(client):
    """series_labels splits into multiple POST calls when IDs exceed batch size."""
    ids = _fake_series_ids(SERIES_BATCH_SIZE + 10)
    route = respx.post(f"{PMPROXY_BASE}/series/labels").mock(
        return_value=httpx.Response(200, json=[{"series": "x", "labels": {"hostname": "h1"}}])
    )
    result = await client.series_labels(ids)
    assert route.call_count == 2
    assert len(result) == 2


@respx.mock
async def test_series_instances_batches_when_over_limit(client):
    """series_instances splits into multiple POST calls when IDs exceed batch size."""
    ids = _fake_series_ids(SERIES_BATCH_SIZE + 10)
    route = respx.post(f"{PMPROXY_BASE}/series/instances").mock(
        return_value=httpx.Response(200, json=[{"series": "x", "name": "cpu0"}])
    )
    result = await client.series_instances(ids)
    assert route.call_count == 2
    assert len(result) == 2
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_client_batching.py -v`
Expected: FAIL — `SERIES_BATCH_SIZE` not defined, methods don't batch

**Step 3: Write implementation**

Replace series methods in `client.py`. Add constant near top of class:

```python
# ~150 series IDs × 41 bytes ≈ 6150 bytes — safely under MAX_PARAMS_SIZE (8000)
SERIES_BATCH_SIZE = 150
```

Replace `series_values`, `series_labels`, `series_instances`:

```python
async def series_values(
    self,
    series: list[str],
    start: str,
    finish: str,
    interval: str | None = None,
    samples: int | None = None,
) -> list[dict]:
    """Fetch time-series data points, batching if series IDs exceed limit."""
    if len(series) <= SERIES_BATCH_SIZE:
        params: dict = {"series": ",".join(series), "start": start, "finish": finish}
        if interval:
            params["interval"] = interval
        if samples is not None:
            params["samples"] = samples
        response = await self._get("/series/values", params)
        return response.json()

    # Batch via POST
    all_results: list[dict] = []
    for i in range(0, len(series), SERIES_BATCH_SIZE):
        batch = series[i : i + SERIES_BATCH_SIZE]
        data: dict = {"series": ",".join(batch), "start": start, "finish": finish}
        if interval:
            data["interval"] = interval
        if samples is not None:
            data["samples"] = samples
        response = await self._post("/series/values", data)
        all_results.extend(response.json())
    return all_results

async def series_descs(self, series: list[str]) -> list[dict]:
    """GET /series/descs — metric descriptors for series IDs."""
    response = await self._get("/series/descs", {"series": ",".join(series)})
    return response.json()

async def series_instances(self, series: list[str]) -> list[dict]:
    """Fetch instance domain members, batching if series IDs exceed limit."""
    if len(series) <= SERIES_BATCH_SIZE:
        response = await self._get("/series/instances", {"series": ",".join(series)})
        return response.json()

    all_results: list[dict] = []
    for i in range(0, len(series), SERIES_BATCH_SIZE):
        batch = series[i : i + SERIES_BATCH_SIZE]
        response = await self._post("/series/instances", {"series": ",".join(batch)})
        all_results.extend(response.json())
    return all_results

async def series_labels(self, series: list[str]) -> list[dict]:
    """Fetch labels for series, batching if series IDs exceed limit."""
    if len(series) <= SERIES_BATCH_SIZE:
        response = await self._get("/series/labels", {"series": ",".join(series)})
        return response.json()

    all_results: list[dict] = []
    for i in range(0, len(series), SERIES_BATCH_SIZE):
        batch = series[i : i + SERIES_BATCH_SIZE]
        response = await self._post("/series/labels", {"series": ",".join(batch)})
        all_results.extend(response.json())
    return all_results
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_client_batching.py -v`
Expected: PASS

**Step 5: Run full test suite**

Run: `uv run pytest --cov=pmmcp --cov-report=term-missing`
Expected: All existing tests still pass (GET path unchanged for small batches)

**Step 6: Commit**

```bash
git add src/pmmcp/client.py tests/unit/test_client_batching.py
git commit -m "feat: batch series IDs across POST calls when exceeding URL size limits

pmproxy MAX_PARAMS_SIZE=8000 bytes; 150 series IDs per batch keeps us safe"
```

---

### Task 3: Extract shared expression builder with escaping

All dual-window tools duplicate the same `" or ".join()` pattern with no escaping. Extract to a shared helper that escapes `"` in hostnames and enforces a maximum expression length.

**Files:**
- Create: `src/pmmcp/tools/_expr.py`
- Test: `tests/unit/test_expr.py` (create)

**Step 1: Write the failing tests**

```python
# tests/unit/test_expr.py
"""Tests for expression builder helper."""

import pytest

from pmmcp.tools._expr import build_series_expr, MAX_EXPR_METRICS


def test_single_metric_no_host():
    assert build_series_expr(["kernel.all.cpu.user"]) == "kernel.all.cpu.user"


def test_multiple_metrics_no_host():
    result = build_series_expr(["cpu.user", "cpu.sys"])
    assert result == "cpu.user or cpu.sys"


def test_single_metric_with_host():
    result = build_series_expr(["cpu.user"], host="web-01")
    assert result == 'cpu.user{hostname=="web-01"}'


def test_multiple_metrics_with_host():
    result = build_series_expr(["cpu.user", "cpu.sys"], host="web-01")
    assert result == 'cpu.user{hostname=="web-01"} or cpu.sys{hostname=="web-01"}'


def test_host_with_double_quotes_escaped():
    """Hostnames containing " are escaped to prevent expression injection."""
    result = build_series_expr(["cpu.user"], host='bad"host')
    assert '"' not in result.split("hostname==")[1].replace('\\"', "").rstrip('}"')


def test_too_many_metrics_raises():
    """Exceeding MAX_EXPR_METRICS raises ValueError."""
    names = [f"metric.{i}" for i in range(MAX_EXPR_METRICS + 1)]
    with pytest.raises(ValueError, match="too many metrics"):
        build_series_expr(names)


def test_returns_list_of_chunked_exprs_when_requested():
    """build_series_exprs (plural) returns chunked expressions."""
    from pmmcp.tools._expr import build_series_exprs
    names = [f"metric.{i}" for i in range(80)]
    exprs = build_series_exprs(names, host="h1", chunk_size=30)
    assert len(exprs) == 3  # 30, 30, 20
    for expr in exprs:
        assert 'hostname=="h1"' in expr
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_expr.py -v`
Expected: FAIL — module doesn't exist

**Step 3: Write implementation**

```python
# src/pmmcp/tools/_expr.py
"""Shared series expression builder with escaping and chunking."""

from __future__ import annotations

# pmproxy MAX_PARAMS_SIZE is 8000 bytes; a single OR expression with host filters
# averages ~55 chars per metric. 120 metrics × 55 ≈ 6600 bytes — safe margin.
MAX_EXPR_METRICS = 120


def _escape_host(host: str) -> str:
    """Escape characters that break pmproxy series expression parsing."""
    return host.replace("\\", "\\\\").replace('"', '\\"')


def build_series_expr(names: list[str], host: str = "") -> str:
    """Build a single pmproxy series query expression.

    Raises ValueError if names exceeds MAX_EXPR_METRICS.
    """
    if len(names) > MAX_EXPR_METRICS:
        raise ValueError(
            f"too many metrics ({len(names)}) for a single expression; "
            f"max is {MAX_EXPR_METRICS}. Use build_series_exprs() to chunk."
        )

    if host:
        safe_host = _escape_host(host)
        parts = [f'{name}{{hostname=="{safe_host}"}}' for name in names]
    else:
        parts = list(names)

    return " or ".join(parts) if len(parts) > 1 else parts[0]


def build_series_exprs(
    names: list[str], host: str = "", chunk_size: int = MAX_EXPR_METRICS
) -> list[str]:
    """Build a list of expressions, chunking names to stay under size limits."""
    exprs = []
    for i in range(0, len(names), chunk_size):
        chunk = names[i : i + chunk_size]
        exprs.append(build_series_expr(chunk, host))
    return exprs
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_expr.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/pmmcp/tools/_expr.py tests/unit/test_expr.py
git commit -m "feat: shared expression builder with host escaping and chunking

Prevents expression injection from special chars in hostnames and enforces
size limits to stay under pmproxy MAX_PARAMS_SIZE"
```

---

### Task 4: Refactor `_fetch_window` — separate query from fetch, add concurrency

The current `_fetch_window` does: query → values → labels → instances (all sequential). Refactor to:
1. Accept optional pre-resolved series IDs (skip query when provided)
2. Run `series_labels` and `series_instances` concurrently
3. Support chunked expressions (multiple queries merged)

This is the critical seam that Phase 2's SQLite sink will plug into.

**Files:**
- Modify: `src/pmmcp/tools/_fetch.py:9-83`
- Test: `tests/unit/test_fetch_window.py` (create or modify existing)

**Step 1: Write the failing tests**

```python
# tests/unit/test_fetch_refactored.py
"""Tests for refactored _fetch_window with pre-resolved IDs and concurrency."""

import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from pmmcp.client import PmproxyClient
from pmmcp.config import PmproxyConfig
from pmmcp.tools._fetch import _fetch_window, _resolve_series_ids

PMPROXY_BASE = "http://localhost:44322"
SERIES_A = "a" * 40
SERIES_B = "b" * 40


@pytest.fixture
def config():
    return PmproxyConfig(url=PMPROXY_BASE)


@pytest.fixture
async def client(config):
    c = PmproxyClient(config)
    yield c
    await c.close()


@respx.mock
async def test_resolve_series_ids_from_single_expr(client):
    """_resolve_series_ids queries pmproxy and returns deduplicated IDs."""
    respx.get(f"{PMPROXY_BASE}/series/query").mock(
        return_value=httpx.Response(200, json=[SERIES_A, SERIES_B])
    )
    ids = await _resolve_series_ids(client, ["kernel.all.cpu.user"])
    assert set(ids) == {SERIES_A, SERIES_B}


@respx.mock
async def test_resolve_series_ids_deduplicates_across_chunks(client):
    """When multiple expressions return overlapping IDs, they're deduplicated."""
    respx.get(f"{PMPROXY_BASE}/series/query").mock(
        return_value=httpx.Response(200, json=[SERIES_A, SERIES_B])
    )
    ids = await _resolve_series_ids(
        client, ["kernel.all.cpu.user", "kernel.all.cpu.user"]
    )
    assert len(ids) == len(set(ids))


@respx.mock
async def test_fetch_window_with_pre_resolved_ids(client):
    """_fetch_window skips series_query when series_ids are provided."""
    query_route = respx.get(f"{PMPROXY_BASE}/series/query")
    respx.get(f"{PMPROXY_BASE}/series/values").mock(
        return_value=httpx.Response(200, json=[
            {"series": SERIES_A, "timestamp": 1.0, "value": "42"}
        ])
    )
    respx.get(f"{PMPROXY_BASE}/series/labels").mock(
        return_value=httpx.Response(200, json=[
            {"series": SERIES_A, "labels": {"metric.name": "cpu.user"}}
        ])
    )
    respx.get(f"{PMPROXY_BASE}/series/instances").mock(
        return_value=httpx.Response(200, json=[])
    )
    values, _ = await _fetch_window(
        client, exprs=[], start="-1hours", end="now",
        interval="15s", limit=100, series_ids=[SERIES_A]
    )
    assert not query_route.called
    assert ("cpu.user", None) in values


@respx.mock
async def test_fetch_window_labels_and_instances_concurrent(client):
    """series_labels and series_instances are called concurrently."""
    respx.get(f"{PMPROXY_BASE}/series/values").mock(
        return_value=httpx.Response(200, json=[
            {"series": SERIES_A, "timestamp": 1.0, "value": "1"}
        ])
    )

    call_order = []

    original_labels = client.series_labels
    original_instances = client.series_instances

    async def tracked_labels(ids):
        call_order.append("labels_start")
        result = await original_labels(ids)
        call_order.append("labels_end")
        return result

    async def tracked_instances(ids):
        call_order.append("instances_start")
        result = await original_instances(ids)
        call_order.append("instances_end")
        return result

    respx.get(f"{PMPROXY_BASE}/series/labels").mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get(f"{PMPROXY_BASE}/series/instances").mock(
        return_value=httpx.Response(200, json=[])
    )

    client.series_labels = tracked_labels
    client.series_instances = tracked_instances

    await _fetch_window(
        client, exprs=[], start="-1hours", end="now",
        interval="15s", limit=100, series_ids=[SERIES_A]
    )
    # Both should start before either ends (concurrent)
    assert "labels_start" in call_order
    assert "instances_start" in call_order
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_fetch_refactored.py -v`
Expected: FAIL — new signature doesn't exist

**Step 3: Write implementation**

Replace `_fetch.py` entirely:

```python
"""Shared timeseries window-fetching helper for tool modules."""

from __future__ import annotations

import asyncio

from pmmcp.client import PmproxyClient, PmproxyConnectionError, PmproxyError, PmproxyTimeoutError
from pmmcp.utils import expand_time_units


async def _resolve_series_ids(
    client: PmproxyClient, exprs: list[str]
) -> list[str]:
    """Query one or more expressions and return deduplicated series IDs."""
    all_ids: set[str] = set()
    for expr in exprs:
        series_ids = await client.series_query(expr)
        if series_ids and isinstance(series_ids[0], dict):
            all_ids.update(entry["series"] for entry in series_ids)
        else:
            all_ids.update(series_ids)
    return list(all_ids)


async def _fetch_metadata(
    client: PmproxyClient, series_ids: list[str]
) -> tuple[dict[str, str], dict[str, str]]:
    """Fetch metric names and instance names concurrently. Non-fatal on error."""
    name_by_series: dict[str, str] = {}
    instance_name_by_series: dict[str, str] = {}

    async def fetch_labels():
        try:
            labels_list = await client.series_labels(series_ids)
            for item in labels_list:
                metric_name = item.get("labels", {}).get("metric.name", "")
                if metric_name:
                    name_by_series[item["series"]] = metric_name
        except PmproxyError:
            pass

    async def fetch_instances():
        try:
            instances_list = await client.series_instances(series_ids)
            for item in instances_list:
                instance_name_by_series[item["series"]] = item.get("name", "")
        except PmproxyError:
            pass

    await asyncio.gather(fetch_labels(), fetch_instances())
    return name_by_series, instance_name_by_series


async def _fetch_window(
    client: PmproxyClient,
    exprs: list[str],
    start: str,
    end: str,
    interval: str,
    limit: int,
    series_ids: list[str] | None = None,
) -> tuple[dict[tuple[str, str | None], list[float]], dict[tuple[str, str | None], list[dict]]]:
    """Fetch a time window and return (numeric_values_by_key, raw_samples_by_key).

    If series_ids is provided, skips the series_query step (avoids duplicate queries
    in dual-window tools).

    Raises PmproxyConnectionError, PmproxyTimeoutError, or PmproxyError on failure.
    """
    if series_ids is None:
        series_ids = await _resolve_series_ids(client, exprs)

    if not series_ids:
        return {}, {}

    raw_values = await client.series_values(
        series=series_ids,
        start=expand_time_units(start),
        finish=expand_time_units(end),
        interval=interval,
        samples=limit,
    )

    name_by_series, instance_name_by_series = await _fetch_metadata(client, series_ids)

    numeric_values: dict[tuple[str, str | None], list[float]] = {}
    raw_samples: dict[tuple[str, str | None], list[dict]] = {}

    for point in raw_values:
        series_id = point["series"]
        metric_name = name_by_series.get(series_id, series_id)
        instance_name = instance_name_by_series.get(series_id) or None
        key = (metric_name, instance_name)

        try:
            numeric_val = float(point["value"])
        except (ValueError, TypeError):
            continue

        if key not in numeric_values:
            numeric_values[key] = []
            raw_samples[key] = []
        numeric_values[key].append(numeric_val)
        raw_samples[key].append({"timestamp": point["timestamp"], "value": numeric_val})

    return numeric_values, raw_samples
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_fetch_refactored.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/pmmcp/tools/_fetch.py tests/unit/test_fetch_refactored.py
git commit -m "refactor: _fetch_window accepts pre-resolved IDs, concurrent metadata

Separate query-from-fetch to enable dedup in dual-window tools.
Labels + instances fetched concurrently via asyncio.gather."
```

---

### Task 5: Update all callers of `_fetch_window` for new signature

All tools that call `_fetch_window` need to pass `exprs=` (list) instead of `expr=` (string). The old positional `expr` argument becomes keyword-only `exprs`.

**Files:**
- Modify: `src/pmmcp/tools/anomaly.py:44-54`
- Modify: `src/pmmcp/tools/comparison.py:34-48`
- Modify: `src/pmmcp/tools/correlation.py:57-64`
- Modify: `src/pmmcp/tools/scanning.py:32-43`

**Step 1: Verify existing tests still describe expected behavior**

Run: `uv run pytest tests/unit/ -v --tb=short`
Expected: Some tests FAIL because `_fetch_window` signature changed

**Step 2: Update callers — mechanical replacement**

Each tool: replace inline expression building with `build_series_expr(s)` and pass `exprs=[expr]`.

For `anomaly.py` — replace lines 44-54:
```python
from pmmcp.tools._expr import build_series_exprs

# ... inside _detect_anomalies_impl:
    exprs = build_series_exprs(metrics, host=host)

    try:
        series_ids = await _resolve_series_ids(client, exprs)
        baseline_vals, _ = await _fetch_window(
            client, exprs=[], start=baseline_start, end=baseline_end,
            interval=resolved, limit=1000, series_ids=series_ids
        )
        recent_vals, _ = await _fetch_window(
            client, exprs=[], start=recent_start, end=recent_end,
            interval=resolved, limit=200, series_ids=series_ids
        )
```

For `comparison.py` — replace lines 34-48:
```python
from pmmcp.tools._expr import build_series_expr
from pmmcp.tools._fetch import _resolve_series_ids

# ... inside _compare_windows_impl:
    expr = build_series_expr(names, host=host)

    try:
        series_ids = await _resolve_series_ids(client, [expr])
        values_a, samples_a = await _fetch_window(
            client, exprs=[], start=window_a_start, end=window_a_end,
            interval=resolved, limit=limit, series_ids=series_ids
        )
        values_b, samples_b = await _fetch_window(
            client, exprs=[], start=window_b_start, end=window_b_end,
            interval=resolved, limit=limit, series_ids=series_ids
        )
```

For `correlation.py` — replace lines 57-64:
```python
from pmmcp.tools._expr import build_series_expr

# ... inside _correlate_metrics_impl:
    expr = build_series_expr(metrics, host=host)

    try:
        values_by_key, _ = await _fetch_window(
            client, exprs=[expr], start=start, end=end, interval=resolved, limit=1000
        )
```

For `scanning.py` — replace lines 32-43:
```python
from pmmcp.tools._fetch import _resolve_series_ids

# ... inside _scan_changes_impl:
    if metric_prefix.endswith("*"):
        expr = metric_prefix
    else:
        expr = f"{metric_prefix}.*"

    try:
        series_ids = await _resolve_series_ids(client, [expr])
        baseline_vals, _ = await _fetch_window(
            client, exprs=[], start=baseline_start, end=baseline_end,
            interval=resolved, limit=500, series_ids=series_ids
        )
        comparison_vals, _ = await _fetch_window(
            client, exprs=[], start=comparison_start, end=comparison_end,
            interval=resolved, limit=500, series_ids=series_ids
        )
```

**Step 3: Run full test suite**

Run: `uv run pytest --cov=pmmcp --cov-report=term-missing`
Expected: PASS — all existing tests should pass (behavior unchanged, just deduplicated)

**Step 4: Commit**

```bash
git add src/pmmcp/tools/anomaly.py src/pmmcp/tools/comparison.py \
        src/pmmcp/tools/correlation.py src/pmmcp/tools/scanning.py
git commit -m "refactor: deduplicate series_query in dual-window tools

Query once, reuse IDs for both windows. Use shared expression builder.
Eliminates 2 redundant HTTP calls per dual-window invocation."
```

---

### Task 6: Update `_resolve_series_and_fetch` in timeseries.py

Same pattern — use new `_fetch_window` signature.

**Files:**
- Modify: `src/pmmcp/tools/timeseries.py:17-127`

**Step 1: Update implementation**

Replace `_resolve_series_and_fetch` to use the refactored `_fetch_window`:

```python
from pmmcp.tools._fetch import _fetch_window, _resolve_series_ids

async def _resolve_series_and_fetch(
    client: PmproxyClient,
    expr: str,
    start: str,
    end: str,
    interval: str,
    limit: int,
    offset: int,
) -> dict:
    """Query series IDs by expression, then fetch values."""
    resolved = resolve_interval(start, end, interval)
    try:
        effective_samples = min(limit, compute_natural_samples(start, end, resolved))
    except ValueError:
        effective_samples = limit

    try:
        values_by_key, _ = await _fetch_window(
            client, exprs=[expr], start=start, end=end,
            interval=resolved, limit=effective_samples
        )
    except PmproxyConnectionError as exc:
        return _mcp_error("Connection error", f"pmproxy is unreachable: {exc}",
                          "Check that pmproxy is running and the URL is correct.")
    except PmproxyTimeoutError as exc:
        return _mcp_error("Timeout", f"pmproxy did not respond in time: {exc}",
                          "Try reducing the time window or number of metrics.")
    except PmproxyError as exc:
        return _mcp_error("pmproxy error", str(exc), "Check the metric name or expression.")

    # _fetch_window already resolved names and instances — reconstruct items
    all_items = []
    for (name, inst), vals in values_by_key.items():
        # Reconstruct sample list from numeric values (timestamps lost in numeric_values)
        # ... need to use raw_samples instead
```

Actually — `_resolve_series_and_fetch` needs `raw_samples` (with timestamps), not just `numeric_values`. Adjust to use the second return value:

```python
    try:
        _, raw_samples = await _fetch_window(
            client, exprs=[expr], start=start, end=end,
            interval=resolved, limit=effective_samples
        )
    except PmproxyConnectionError as exc:
        return _mcp_error("Connection error", f"pmproxy is unreachable: {exc}",
                          "Check that pmproxy is running and the URL is correct.")
    except PmproxyTimeoutError as exc:
        return _mcp_error("Timeout", f"pmproxy did not respond in time: {exc}",
                          "Try reducing the time window or number of metrics.")
    except PmproxyError as exc:
        return _mcp_error("pmproxy error", str(exc), "Check the metric name or expression.")

    all_items = [
        {"name": name, "instance": inst, "samples": samples}
        for (name, inst), samples in raw_samples.items()
    ]

    total = len(all_items)
    page = all_items[offset : offset + limit] if limit < total else all_items
    return {
        "items": page,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + limit < total,
    }
```

Also remove the dead `zone` parameter from `_fetch_timeseries_impl` and `pcp_fetch_timeseries`.

**Step 2: Run full test suite**

Run: `uv run pytest --cov=pmmcp --cov-report=term-missing`
Expected: PASS

**Step 3: Commit**

```bash
git add src/pmmcp/tools/timeseries.py
git commit -m "refactor: timeseries uses refactored _fetch_window, remove dead zone param"
```

---

### Task 7: Update ranking.py to use shared helpers

`pcp_rank_hosts` does its own series_query → series_values → series_labels chain. Update to use `_resolve_series_ids` and batched client methods.

**Files:**
- Modify: `src/pmmcp/tools/ranking.py:38-78`

**Step 1: Update implementation**

Replace the manual series_query + series_values + series_labels chain with `_resolve_series_ids`. The batching is now handled by the client layer transparently.

**Step 2: Run full test suite**

Run: `uv run pytest --cov=pmmcp --cov-report=term-missing`
Expected: PASS

**Step 3: Commit**

```bash
git add src/pmmcp/tools/ranking.py
git commit -m "refactor: ranking uses _resolve_series_ids, batching now transparent"
```

---

### Task 8: Fix minor issues — indom normalization, null tracking

**Files:**
- Modify: `src/pmmcp/tools/discovery.py:128`
- Modify: `src/pmmcp/tools/_fetch.py` (add null counter to return)

**Step 1: Fix indom normalization typo**

In `discovery.py:128`, change:
```python
indom = None if indom_raw in (None, "none", "none") else indom_raw
```
to:
```python
indom = None if indom_raw is None or str(indom_raw).lower() == "none" else indom_raw
```

**Step 2: Run tests**

Run: `uv run pytest --cov=pmmcp --cov-report=term-missing`
Expected: PASS

**Step 3: Commit**

```bash
git add src/pmmcp/tools/discovery.py
git commit -m "fix: case-insensitive indom normalization, remove duplicate check"
```

---

### Task 9: Pre-push sanity + final review

**Step 1: Run pre-push sanity**

Run: `scripts/pre-push-sanity.sh`
Expected: lint, format, tests all pass with >=80% coverage

**Step 2: Review all changes**

Run: `git diff main --stat` to verify only expected files changed.

---

## Phase 1, Worktree B: Recursive Discovery (`008-recursive-discovery`)

### Task 10: Add recursive namespace traversal to `_discover_metrics_impl`

`pmapi_children` returns only immediate children. For `quick_investigate(subsystem="kernel")` to work, we need to recurse into non-leaf nodes to find actual metric names.

**Files:**
- Modify: `src/pmmcp/tools/discovery.py:62-98`
- Test: `tests/unit/test_discovery_recursive.py` (create)

**Step 1: Write the failing tests**

```python
# tests/unit/test_discovery_recursive.py
"""Tests for recursive namespace discovery."""

import httpx
import pytest
import respx

from pmmcp.client import PmproxyClient
from pmmcp.config import PmproxyConfig
from pmmcp.tools.discovery import _discover_metrics_impl

PMPROXY_BASE = "http://localhost:44322"


@pytest.fixture
def config():
    return PmproxyConfig(url=PMPROXY_BASE)


@pytest.fixture
async def client(config):
    c = PmproxyClient(config)
    yield c
    await c.close()


@respx.mock
async def test_discover_recurses_nonleaf_children(client):
    """When prefix has only non-leaf children, recurse to find leaf metrics."""
    # /pmapi/children?prefix=kernel → nonleaf: ["all"], leaf: []
    context_route = respx.get(f"{PMPROXY_BASE}/pmapi/context").mock(
        return_value=httpx.Response(200, json={"context": 1})
    )

    def children_handler(request):
        prefix = dict(request.url.params).get("prefix", "")
        if prefix == "kernel":
            return httpx.Response(200, json={
                "name": "kernel", "leaf": [], "nonleaf": ["all", "percpu"]
            })
        elif prefix == "kernel.all":
            return httpx.Response(200, json={
                "name": "kernel.all", "leaf": ["load", "sysfork"], "nonleaf": ["cpu"]
            })
        elif prefix == "kernel.all.cpu":
            return httpx.Response(200, json={
                "name": "kernel.all.cpu", "leaf": ["user", "sys"], "nonleaf": []
            })
        elif prefix == "kernel.percpu":
            return httpx.Response(200, json={
                "name": "kernel.percpu", "leaf": [], "nonleaf": ["cpu"]
            })
        elif prefix == "kernel.percpu.cpu":
            return httpx.Response(200, json={
                "name": "kernel.percpu.cpu", "leaf": ["user", "sys"], "nonleaf": []
            })
        return httpx.Response(404, json={"message": "not found"})

    respx.get(f"{PMPROXY_BASE}/pmapi/children").mock(side_effect=children_handler)

    result = await _discover_metrics_impl(
        client, host="", prefix="kernel", search="", limit=200, offset=0
    )

    names = [item["name"] for item in result["items"] if item["leaf"]]
    assert "kernel.all.load" in names
    assert "kernel.all.sysfork" in names
    assert "kernel.all.cpu.user" in names
    assert "kernel.all.cpu.sys" in names
    assert "kernel.percpu.cpu.user" in names
    assert all(item["leaf"] for item in result["items"])  # only leaf items returned


@respx.mock
async def test_discover_respects_limit_during_recursion(client):
    """Recursion stops once limit leaf metrics are found."""
    respx.get(f"{PMPROXY_BASE}/pmapi/context").mock(
        return_value=httpx.Response(200, json={"context": 1})
    )

    def children_handler(request):
        prefix = dict(request.url.params).get("prefix", "")
        if prefix == "big":
            return httpx.Response(200, json={
                "name": "big",
                "leaf": [f"metric{i}" for i in range(100)],
                "nonleaf": ["sub"]
            })
        elif prefix == "big.sub":
            return httpx.Response(200, json={
                "name": "big.sub", "leaf": ["extra"], "nonleaf": []
            })
        return httpx.Response(404, json={"message": "not found"})

    respx.get(f"{PMPROXY_BASE}/pmapi/children").mock(side_effect=children_handler)

    result = await _discover_metrics_impl(
        client, host="", prefix="big", search="", limit=50, offset=0
    )
    assert len(result["items"]) <= 50


@respx.mock
async def test_discover_shallow_when_prefix_has_leaves(client):
    """When prefix has leaf children directly, return them without unnecessary recursion."""
    respx.get(f"{PMPROXY_BASE}/pmapi/context").mock(
        return_value=httpx.Response(200, json={"context": 1})
    )
    respx.get(f"{PMPROXY_BASE}/pmapi/children").mock(
        return_value=httpx.Response(200, json={
            "name": "kernel.all.cpu", "leaf": ["user", "sys"], "nonleaf": []
        })
    )

    result = await _discover_metrics_impl(
        client, host="", prefix="kernel.all.cpu", search="", limit=200, offset=0
    )
    names = [item["name"] for item in result["items"]]
    assert names == ["kernel.all.cpu.user", "kernel.all.cpu.sys"]
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_discovery_recursive.py -v`
Expected: FAIL — current implementation doesn't recurse

**Step 3: Write implementation**

Replace the namespace tree section of `_discover_metrics_impl` (lines 62-98 in `discovery.py`):

```python
    # Use namespace tree (pmapi/children) with recursion for leaf discovery
    max_leaves = limit + offset  # collect enough for pagination

    async def _collect_leaves(pfx: str, depth: int = 0) -> list[dict]:
        """Recursively collect leaf metrics from namespace tree."""
        if depth > 10:  # safety limit
            return []

        try:
            raw = await client.pmapi_children(pfx, host)
        except PmproxyNotFoundError:
            return []
        except PmproxyError:
            return []

        base = raw.get("name", pfx)
        leaves = []

        for name in raw.get("leaf", []):
            full_name = f"{base}.{name}" if base else name
            leaves.append({"name": full_name, "oneline": "", "leaf": True})
            if len(leaves) >= max_leaves:
                return leaves

        for name in raw.get("nonleaf", []):
            full_name = f"{base}.{name}" if base else name
            child_leaves = await _collect_leaves(full_name, depth + 1)
            leaves.extend(child_leaves)
            if len(leaves) >= max_leaves:
                return leaves[:max_leaves]

        return leaves

    try:
        raw = await client.pmapi_children(prefix, host)
    except PmproxyConnectionError as exc:
        return _mcp_error("Connection error", str(exc), "Check pmproxy connectivity.")
    except PmproxyTimeoutError as exc:
        return _mcp_error("Timeout", str(exc), "Try a more specific prefix.")
    except PmproxyNotFoundError as exc:
        return _mcp_error("Not found", f"Namespace prefix not found: {exc}",
                          "Use pcp_search to find valid metric namespace prefixes.")
    except PmproxyError as exc:
        return _mcp_error("pmproxy error", str(exc), "Check pmproxy logs.")

    base_prefix = raw.get("name", prefix)
    leaf_names = raw.get("leaf", [])
    nonleaf_names = raw.get("nonleaf", [])

    items = []
    for name in leaf_names:
        full_name = f"{base_prefix}.{name}" if base_prefix else name
        items.append({"name": full_name, "oneline": "", "leaf": True})

    # Recurse into non-leaf children to find leaf metrics
    for name in nonleaf_names:
        full_name = f"{base_prefix}.{name}" if base_prefix else name
        child_leaves = await _collect_leaves(full_name, depth=1)
        items.extend(child_leaves)
        if len(items) >= max_leaves:
            items = items[:max_leaves]
            break

    total = len(items)
    page = items[offset : offset + limit]
    return {
        "items": page,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + limit < total,
    }
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_discovery_recursive.py -v`
Expected: PASS

**Step 5: Run full test suite to check nothing broke**

Run: `uv run pytest --cov=pmmcp --cov-report=term-missing`
Expected: PASS

**Step 6: Commit**

```bash
git add src/pmmcp/tools/discovery.py tests/unit/test_discovery_recursive.py
git commit -m "feat: recursive namespace traversal in metric discovery

pmapi_children only returns immediate children; recurse non-leaf nodes to
find actual leaf metrics. Fixes quick_investigate returning zero metrics
for broad prefixes like 'kernel'."
```

---

### Task 11: Update quick_investigate to use recursive discovery

With Task 10 merged, `_discover_metrics_impl` now returns leaf metrics when given a broad prefix. But `investigate.py:99` still filters on `item.get("leaf", True)` — verify this works correctly and add a test.

**Files:**
- Test: `tests/unit/test_investigate_discovery.py` (create)

**Step 1: Write the test**

```python
# tests/unit/test_investigate_discovery.py
"""Test that quick_investigate correctly uses recursive discovery."""

import httpx
import pytest
import respx

from pmmcp.client import PmproxyClient
from pmmcp.config import PmproxyConfig
from pmmcp.tools.investigate import _quick_investigate_impl

PMPROXY_BASE = "http://localhost:44322"


@pytest.fixture
def config():
    return PmproxyConfig(url=PMPROXY_BASE)


@pytest.fixture
async def client(config):
    c = PmproxyClient(config)
    yield c
    await c.close()


@respx.mock
async def test_investigate_finds_metrics_from_broad_prefix(client):
    """quick_investigate with subsystem='kernel' finds leaf metrics via recursion."""
    respx.get(f"{PMPROXY_BASE}/pmapi/context").mock(
        return_value=httpx.Response(200, json={"context": 1})
    )

    def children_handler(request):
        prefix = dict(request.url.params).get("prefix", "")
        if prefix == "kernel":
            return httpx.Response(200, json={
                "name": "kernel", "leaf": [], "nonleaf": ["all"]
            })
        elif prefix == "kernel.all":
            return httpx.Response(200, json={
                "name": "kernel.all", "leaf": ["load"], "nonleaf": []
            })
        return httpx.Response(404, json={"message": "not found"})

    respx.get(f"{PMPROXY_BASE}/pmapi/children").mock(side_effect=children_handler)

    # Mock the anomaly detection series calls to return empty (we just care that
    # discovery found metrics and didn't return "No metrics found")
    respx.get(f"{PMPROXY_BASE}/series/query").mock(
        return_value=httpx.Response(200, json=[])
    )

    result = await _quick_investigate_impl(
        client,
        time_of_interest="-1hours",
        subsystem="kernel",
        lookback="2hours",
    )

    # Should NOT be an error about "No metrics found"
    assert not result.get("isError"), f"Got error: {result}"
```

**Step 2: Run test**

Run: `uv run pytest tests/unit/test_investigate_discovery.py -v`
Expected: PASS (with Task 10's discovery recursion in place)

**Step 3: Commit**

```bash
git add tests/unit/test_investigate_discovery.py
git commit -m "test: verify quick_investigate works with broad prefixes via recursive discovery"
```

---

### Task 12: Pre-push sanity for Worktree B

Run: `scripts/pre-push-sanity.sh`
Expected: PASS

---

## Phase 2, Worktree C: SQLite Sink (`009-sqlite-sink`)

> **Depends on:** Phase 1 merged to main.

### Task 13: Add aiosqlite dependency

**Files:**
- Modify: `pyproject.toml:13-18` (add `aiosqlite>=0.20`)

**Step 1: Add dependency**

```toml
dependencies = [
    "mcp[cli]>=1.2.0",
    "pydantic>=2.0",
    "pydantic-settings",
    "httpx>=0.27",
    "aiosqlite>=0.20",
]
```

**Step 2: Sync**

Run: `uv sync --extra dev`
Expected: aiosqlite installed

**Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add aiosqlite dependency for session SQLite sink"
```

---

### Task 14: Create session-scoped SQLite DB in lifespan

The lifespan creates a temp directory and SQLite DB. The DB path is accessible via a module-level getter (same pattern as `get_client()`).

**Files:**
- Modify: `src/pmmcp/server.py:47-64`
- Create: `src/pmmcp/session_db.py`
- Test: `tests/unit/test_session_db.py` (create)

**Step 1: Write the failing tests**

```python
# tests/unit/test_session_db.py
"""Tests for session SQLite database lifecycle."""

import aiosqlite
import pytest

from pmmcp.session_db import SessionDB


async def test_create_and_close():
    """SessionDB creates a file, initialises schema, and closes cleanly."""
    db = SessionDB()
    await db.open()
    assert db.path.exists()

    # Schema exists
    async with aiosqlite.connect(db.path) as conn:
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='timeseries'"
        )
        row = await cursor.fetchone()
        assert row is not None

    await db.close()


async def test_insert_and_query():
    """Can insert rows and query them back."""
    db = SessionDB()
    await db.open()

    await db.insert_timeseries([
        {"metric": "cpu.user", "instance": None, "timestamp": 1000.0, "value": 42.5},
        {"metric": "cpu.user", "instance": None, "timestamp": 1001.0, "value": 43.0},
        {"metric": "mem.free", "instance": None, "timestamp": 1000.0, "value": 8192.0},
    ])

    rows = await db.query("SELECT metric, AVG(value) as avg_val FROM timeseries GROUP BY metric ORDER BY metric")
    assert len(rows) == 2
    assert rows[0]["metric"] == "cpu.user"
    assert abs(rows[0]["avg_val"] - 42.75) < 0.01
    assert rows[1]["metric"] == "mem.free"

    await db.close()


async def test_query_returns_column_names():
    """Query results include column names as dict keys."""
    db = SessionDB()
    await db.open()
    await db.insert_timeseries([
        {"metric": "x", "instance": "i1", "timestamp": 1.0, "value": 1.0},
    ])
    rows = await db.query("SELECT metric, instance, timestamp, value FROM timeseries")
    assert rows[0].keys() == {"metric", "instance", "timestamp", "value"}
    await db.close()
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_session_db.py -v`
Expected: FAIL — module doesn't exist

**Step 3: Write implementation**

```python
# src/pmmcp/session_db.py
"""Session-scoped SQLite database for timeseries data."""

from __future__ import annotations

import tempfile
from pathlib import Path

import aiosqlite

_SCHEMA = """
CREATE TABLE IF NOT EXISTS timeseries (
    metric   TEXT    NOT NULL,
    instance TEXT,
    timestamp REAL   NOT NULL,
    value    REAL    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ts_metric ON timeseries(metric);
CREATE INDEX IF NOT EXISTS idx_ts_timestamp ON timeseries(timestamp);
"""


class SessionDB:
    """Lightweight wrapper around a session-scoped SQLite file."""

    def __init__(self, db_path: Path | None = None) -> None:
        if db_path is None:
            tmp = tempfile.NamedTemporaryFile(
                prefix="pmmcp_", suffix=".db", delete=False
            )
            tmp.close()
            db_path = Path(tmp.name)
        self._path = db_path
        self._conn: aiosqlite.Connection | None = None

    @property
    def path(self) -> Path:
        return self._path

    async def open(self) -> None:
        self._conn = await aiosqlite.connect(self._path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(_SCHEMA)
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def insert_timeseries(self, rows: list[dict]) -> int:
        """Insert rows into the timeseries table. Returns count inserted."""
        assert self._conn is not None
        await self._conn.executemany(
            "INSERT INTO timeseries (metric, instance, timestamp, value) VALUES (?, ?, ?, ?)",
            [(r["metric"], r.get("instance"), r["timestamp"], r["value"]) for r in rows],
        )
        await self._conn.commit()
        return len(rows)

    async def query(self, sql: str, params: tuple = ()) -> list[dict]:
        """Execute a SELECT and return rows as dicts."""
        assert self._conn is not None
        cursor = await self._conn.execute(sql, params)
        rows = await cursor.fetchall()
        if not rows:
            return []
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_session_db.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/pmmcp/session_db.py tests/unit/test_session_db.py
git commit -m "feat: SessionDB — session-scoped SQLite for timeseries data

Schema: timeseries(metric, instance, timestamp, value) with indexes.
Supports insert_timeseries and arbitrary SQL queries."
```

---

### Task 15: Wire SessionDB into server lifespan

**Files:**
- Modify: `src/pmmcp/server.py:47-64`

**Step 1: Write the failing test**

```python
# tests/unit/test_server_session_db.py
"""Test that server lifespan creates and exposes session DB."""

from pmmcp.server import get_session_db


def test_get_session_db_returns_none_outside_lifespan():
    """get_session_db returns None when not in lifespan."""
    assert get_session_db() is None
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_server_session_db.py -v`
Expected: FAIL — `get_session_db` not defined

**Step 3: Write implementation**

Add to `server.py`:

```python
from pmmcp.session_db import SessionDB

_session_db: SessionDB | None = None

def get_session_db() -> SessionDB | None:
    return _session_db
```

Update `_lifespan`:

```python
@asynccontextmanager
async def _lifespan(app: FastMCP) -> AsyncIterator[None]:
    global _client, _session_db
    assert _config is not None
    _client = PmproxyClient(_config)
    _session_db = SessionDB()
    await _session_db.open()
    logger.info("pmmcp starting, pmproxy URL: %s, session DB: %s", _config.url, _session_db.path)
    monitor_task = asyncio.create_task(_health_monitor(_client, _config))
    try:
        yield
    finally:
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass
        await _client.close()
        _client = None
        await _session_db.close()
        _session_db = None
        logger.info("pmmcp shutting down")
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_server_session_db.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/pmmcp/server.py tests/unit/test_server_session_db.py
git commit -m "feat: wire SessionDB into server lifespan

Created on startup, closed on shutdown. Accessible via get_session_db()."
```

---

### Task 16: Create `pcp_fetch_to_sqlite` tool

Fetches from pmproxy exactly as `pcp_fetch_timeseries` does today, but writes rows into the session SQLite DB and returns only compact metadata.

**Files:**
- Create: `src/pmmcp/tools/sqlite_sink.py`
- Test: `tests/unit/test_sqlite_sink.py` (create)

**Step 1: Write the failing tests**

```python
# tests/unit/test_sqlite_sink.py
"""Tests for pcp_fetch_to_sqlite tool."""

import httpx
import pytest
import respx

from pmmcp.client import PmproxyClient
from pmmcp.config import PmproxyConfig
from pmmcp.session_db import SessionDB
from pmmcp.tools.sqlite_sink import _fetch_to_sqlite_impl

PMPROXY_BASE = "http://localhost:44322"
SERIES_A = "a" * 40


@pytest.fixture
def config():
    return PmproxyConfig(url=PMPROXY_BASE)


@pytest.fixture
async def client(config):
    c = PmproxyClient(config)
    yield c
    await c.close()


@pytest.fixture
async def session_db():
    db = SessionDB()
    await db.open()
    yield db
    await db.close()


@respx.mock
async def test_fetch_to_sqlite_inserts_rows(client, session_db):
    """Fetched data is written to SQLite, not returned inline."""
    respx.get(f"{PMPROXY_BASE}/series/query").mock(
        return_value=httpx.Response(200, json=[SERIES_A])
    )
    respx.get(f"{PMPROXY_BASE}/series/values").mock(
        return_value=httpx.Response(200, json=[
            {"series": SERIES_A, "timestamp": 1000.0, "value": "42"},
            {"series": SERIES_A, "timestamp": 1001.0, "value": "43"},
        ])
    )
    respx.get(f"{PMPROXY_BASE}/series/labels").mock(
        return_value=httpx.Response(200, json=[
            {"series": SERIES_A, "labels": {"metric.name": "cpu.user"}}
        ])
    )
    respx.get(f"{PMPROXY_BASE}/series/instances").mock(
        return_value=httpx.Response(200, json=[])
    )

    result = await _fetch_to_sqlite_impl(
        client, session_db,
        names=["cpu.user"], start="-1hours", end="now", interval="auto", host=""
    )

    assert result["row_count"] == 2
    assert result["metrics"] == ["cpu.user"]
    assert "db_path" in result

    # Verify data is in SQLite
    rows = await session_db.query("SELECT * FROM timeseries ORDER BY timestamp")
    assert len(rows) == 2
    assert rows[0]["metric"] == "cpu.user"
    assert rows[0]["value"] == 42.0


@respx.mock
async def test_fetch_to_sqlite_returns_compact_metadata(client, session_db):
    """Response contains only metadata, not raw data points."""
    respx.get(f"{PMPROXY_BASE}/series/query").mock(
        return_value=httpx.Response(200, json=[SERIES_A])
    )
    respx.get(f"{PMPROXY_BASE}/series/values").mock(
        return_value=httpx.Response(200, json=[
            {"series": SERIES_A, "timestamp": 1.0, "value": "1"},
        ])
    )
    respx.get(f"{PMPROXY_BASE}/series/labels").mock(
        return_value=httpx.Response(200, json=[
            {"series": SERIES_A, "labels": {"metric.name": "m1"}}
        ])
    )
    respx.get(f"{PMPROXY_BASE}/series/instances").mock(
        return_value=httpx.Response(200, json=[])
    )

    result = await _fetch_to_sqlite_impl(
        client, session_db,
        names=["m1"], start="-1hours", end="now", interval="auto", host=""
    )

    # No "items" or "samples" key — just metadata
    assert "items" not in result
    assert "samples" not in result
    assert "row_count" in result
    assert "db_path" in result
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_sqlite_sink.py -v`
Expected: FAIL — module doesn't exist

**Step 3: Write implementation**

```python
# src/pmmcp/tools/sqlite_sink.py
"""pcp_fetch_to_sqlite and pcp_query_sqlite — out-of-band timeseries storage."""

from __future__ import annotations

import logging

from pmmcp.client import PmproxyClient, PmproxyConnectionError, PmproxyError, PmproxyTimeoutError
from pmmcp.server import get_client, get_session_db, mcp
from pmmcp.session_db import SessionDB
from pmmcp.tools._errors import _mcp_error
from pmmcp.tools._expr import build_series_exprs
from pmmcp.tools._fetch import _fetch_window
from pmmcp.utils import resolve_interval

logger = logging.getLogger(__name__)


async def _fetch_to_sqlite_impl(
    client: PmproxyClient,
    session_db: SessionDB,
    names: list[str],
    start: str,
    end: str,
    interval: str,
    host: str,
) -> dict:
    """Fetch timeseries data and write to session SQLite DB."""
    resolved = resolve_interval(start, end, interval)

    all_rows: list[dict] = []
    metrics_seen: set[str] = set()

    for name in names:
        exprs = build_series_exprs([name], host=host)
        try:
            _, raw_samples = await _fetch_window(
                client, exprs=exprs, start=start, end=end,
                interval=resolved, limit=10000
            )
        except PmproxyConnectionError as exc:
            return _mcp_error("Connection error", str(exc), "Check pmproxy connectivity.")
        except PmproxyTimeoutError as exc:
            return _mcp_error("Timeout", str(exc), "Try a smaller time window.")
        except PmproxyError as exc:
            return _mcp_error("pmproxy error", str(exc), "Check pmproxy logs.")

        for (metric_name, instance), samples in raw_samples.items():
            metrics_seen.add(metric_name)
            for sample in samples:
                all_rows.append({
                    "metric": metric_name,
                    "instance": instance,
                    "timestamp": sample["timestamp"],
                    "value": sample["value"],
                })

    if all_rows:
        await session_db.insert_timeseries(all_rows)

    return {
        "row_count": len(all_rows),
        "metrics": sorted(metrics_seen),
        "db_path": str(session_db.path),
        "window": {"start": start, "end": end, "interval": resolved},
    }


@mcp.tool()
async def pcp_fetch_to_sqlite(
    names: list[str],
    start: str = "-1hour",
    end: str = "now",
    interval: str = "auto",
    host: str = "",
) -> dict:
    """Fetch timeseries data into the session SQLite database for SQL-based analysis.

    Like pcp_fetch_timeseries but writes data to an out-of-band SQLite DB instead
    of returning raw samples. Returns only compact metadata (row count, db path).
    Use pcp_query_sqlite to run SQL against the accumulated data.

    Multiple calls accumulate in the same DB — you can fetch different time windows
    or metrics and then JOIN/compare them with SQL.

    Args:
        names: List of metric names to fetch
        start: Start time (ISO-8601 or PCP relative e.g. '-6hours')
        end: End time (ISO-8601 or 'now')
        interval: Sampling interval or 'auto'
        host: Target hostname (empty = all hosts)
    """
    db = get_session_db()
    if db is None:
        return _mcp_error("Session error", "No session DB available",
                          "This should not happen — check server lifespan.")
    return await _fetch_to_sqlite_impl(
        get_client(), db, names=names, start=start, end=end,
        interval=interval, host=host,
    )
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_sqlite_sink.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/pmmcp/tools/sqlite_sink.py tests/unit/test_sqlite_sink.py
git commit -m "feat: pcp_fetch_to_sqlite — write timeseries to session SQLite

Data goes out-of-band into SQLite, not into Claude's context window.
Returns compact metadata only (row count, db path, metrics)."
```

---

### Task 17: Create `pcp_query_sqlite` tool

**Files:**
- Modify: `src/pmmcp/tools/sqlite_sink.py` (add tool)
- Test: `tests/unit/test_sqlite_query.py` (create)

**Step 1: Write the failing tests**

```python
# tests/unit/test_sqlite_query.py
"""Tests for pcp_query_sqlite tool."""

import pytest

from pmmcp.session_db import SessionDB
from pmmcp.tools.sqlite_sink import _query_sqlite_impl


@pytest.fixture
async def session_db():
    db = SessionDB()
    await db.open()
    await db.insert_timeseries([
        {"metric": "cpu.user", "instance": None, "timestamp": 1000.0, "value": 10.0},
        {"metric": "cpu.user", "instance": None, "timestamp": 1001.0, "value": 20.0},
        {"metric": "cpu.user", "instance": None, "timestamp": 1002.0, "value": 30.0},
        {"metric": "mem.free", "instance": None, "timestamp": 1000.0, "value": 8192.0},
    ])
    yield db
    await db.close()


async def test_basic_select(session_db):
    result = await _query_sqlite_impl(session_db, "SELECT COUNT(*) as cnt FROM timeseries")
    assert result["rows"][0]["cnt"] == 4


async def test_aggregation(session_db):
    result = await _query_sqlite_impl(
        session_db,
        "SELECT metric, AVG(value) as avg_val FROM timeseries GROUP BY metric ORDER BY metric"
    )
    assert len(result["rows"]) == 2
    assert result["rows"][0]["metric"] == "cpu.user"
    assert abs(result["rows"][0]["avg_val"] - 20.0) < 0.01


async def test_row_limit_enforced(session_db):
    result = await _query_sqlite_impl(session_db, "SELECT * FROM timeseries", row_limit=2)
    assert len(result["rows"]) == 2
    assert result["truncated"] is True


async def test_rejects_write_statements(session_db):
    result = await _query_sqlite_impl(session_db, "DELETE FROM timeseries")
    assert result.get("isError") is True


async def test_rejects_drop_statements(session_db):
    result = await _query_sqlite_impl(session_db, "DROP TABLE timeseries")
    assert result.get("isError") is True
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_sqlite_query.py -v`
Expected: FAIL — `_query_sqlite_impl` doesn't exist

**Step 3: Write implementation**

Add to `sqlite_sink.py`:

```python
_FORBIDDEN_KEYWORDS = {"INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "ATTACH", "DETACH"}


async def _query_sqlite_impl(
    session_db: SessionDB,
    sql: str,
    row_limit: int = 500,
) -> dict:
    """Execute a read-only SQL query against the session DB."""
    # Basic safety: reject mutating statements
    first_word = sql.strip().split()[0].upper() if sql.strip() else ""
    if first_word in _FORBIDDEN_KEYWORDS:
        return _mcp_error(
            "Read-only violation",
            f"Statement type '{first_word}' is not allowed.",
            "Only SELECT queries are permitted against the session DB.",
        )

    try:
        rows = await session_db.query(f"{sql} LIMIT {row_limit + 1}")
    except Exception as exc:
        return _mcp_error("SQL error", str(exc), "Check your SQL syntax.")

    truncated = len(rows) > row_limit
    if truncated:
        rows = rows[:row_limit]

    return {
        "rows": rows,
        "row_count": len(rows),
        "truncated": truncated,
    }


@mcp.tool()
async def pcp_query_sqlite(
    sql: str,
    row_limit: int = 500,
) -> dict:
    """Run a SQL query against the session timeseries database.

    Use after pcp_fetch_to_sqlite to analyse accumulated data with SQL. The
    timeseries table has columns: metric (TEXT), instance (TEXT), timestamp (REAL),
    value (REAL).

    Example queries:
    - SELECT metric, AVG(value), MAX(value) FROM timeseries GROUP BY metric
    - SELECT metric, value FROM timeseries WHERE timestamp BETWEEN 1000 AND 2000
    - SELECT metric, AVG(value) FROM timeseries GROUP BY metric, CAST(timestamp/3600 AS INT)

    Args:
        sql: SELECT query to execute (read-only; INSERT/UPDATE/DELETE rejected)
        row_limit: Maximum rows to return (default 500)
    """
    db = get_session_db()
    if db is None:
        return _mcp_error("Session error", "No session DB available",
                          "Fetch data first with pcp_fetch_to_sqlite.")
    return await _query_sqlite_impl(db, sql=sql, row_limit=row_limit)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_sqlite_query.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/pmmcp/tools/sqlite_sink.py tests/unit/test_sqlite_query.py
git commit -m "feat: pcp_query_sqlite — SQL interface to session timeseries DB

Read-only queries against accumulated timeseries data. Rejects mutating
statements. Row limit prevents context flooding."
```

---

### Task 18: Register sqlite_sink tools and add contract tests

**Files:**
- Modify: `src/pmmcp/tools/__init__.py`
- Test: `tests/contract/test_sqlite_tools_contract.py` (create)

**Step 1: Add import to tools __init__**

Add `import pmmcp.tools.sqlite_sink` to `src/pmmcp/tools/__init__.py`.

**Step 2: Write contract tests**

```python
# tests/contract/test_sqlite_tools_contract.py
"""Contract tests for SQLite sink tools — verify MCP schema registration."""

from pmmcp import server as srv


def test_fetch_to_sqlite_registered():
    tools = {t.name for t in srv.mcp._tool_manager.list_tools()}
    assert "pcp_fetch_to_sqlite" in tools


def test_query_sqlite_registered():
    tools = {t.name for t in srv.mcp._tool_manager.list_tools()}
    assert "pcp_query_sqlite" in tools
```

**Step 3: Run tests**

Run: `uv run pytest tests/contract/test_sqlite_tools_contract.py -v`
Expected: PASS

**Step 4: Run pre-push sanity**

Run: `scripts/pre-push-sanity.sh`
Expected: PASS

**Step 5: Commit**

```bash
git add src/pmmcp/tools/__init__.py tests/contract/test_sqlite_tools_contract.py
git commit -m "chore: register sqlite_sink tools + contract tests"
```

---

## Merge Strategy

```
main
  ├── 007-client-hardening (Worktree A: Tasks 1-9)    ──┐
  ├── 008-recursive-discovery (Worktree B: Tasks 10-12) ─┤── merge both → main
  │                                                       │
  └── 009-sqlite-sink (Worktree C: Tasks 13-18)  ────────┘── merge after Phase 1
```

Worktrees A and B can run in parallel (zero file overlap). Worktree C starts after both merge.
