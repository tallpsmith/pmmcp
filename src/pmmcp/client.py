from __future__ import annotations

import logging

import httpx

from pmmcp.config import PmproxyConfig

logger = logging.getLogger(__name__)

# pmproxy has a ~8KB URL parameter limit (MAX_PARAMS_SIZE).
# Each series ID is a 40-char SHA-1 hex string + comma separator = 41 bytes.
# 150 * 41 ≈ 6150 bytes — safely under the limit with room for other params.
SERIES_BATCH_SIZE = 150


class PmproxyError(Exception):
    """Base exception for pmproxy communication errors."""


class PmproxyConnectionError(PmproxyError):
    """pmproxy is unreachable (connection refused, DNS failure, timeout)."""


class PmproxyNotFoundError(PmproxyError):
    """Requested metric, host, or instance does not exist."""


class PmproxyTimeoutError(PmproxyError):
    """Request to pmproxy exceeded the configured timeout."""


class PmproxyAPIError(PmproxyError):
    """pmproxy returned an error response (HTTP 4xx/5xx with error body)."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(f"pmproxy error {status_code}: {message}")


class PmproxyClient:
    """Async HTTP client for pmproxy REST API."""

    def __init__(self, config: PmproxyConfig) -> None:
        self._config = config
        self._base_url = str(config.url).rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=config.timeout,
        )
        # PMAPI context cache: host -> context_id
        self._contexts: dict[str, int] = {}

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    def _raise_for_response(self, response: httpx.Response) -> None:
        """Translate pmproxy HTTP errors into client exceptions."""
        if response.status_code == 200:
            try:
                body = response.json()
            except Exception:
                return
            if isinstance(body, dict) and body.get("success") is False:
                raise PmproxyAPIError(200, body.get("message", "Unknown error"))
            return

        try:
            body = response.json()
            message = body.get("message", response.text)
        except Exception:
            message = response.text

        if response.status_code == 400:
            if "unknown metric" in message.lower():
                raise PmproxyNotFoundError(message)
            raise PmproxyAPIError(response.status_code, message)
        elif response.status_code == 403:
            raise PmproxyAPIError(response.status_code, message)
        elif response.status_code == 404:
            raise PmproxyNotFoundError(message)
        else:
            raise PmproxyAPIError(response.status_code, message)

    async def _get(self, path: str, params: dict | None = None) -> httpx.Response:
        try:
            response = await self._client.get(path, params=params)
        except httpx.ConnectError as exc:
            raise PmproxyConnectionError(str(exc)) from exc
        except httpx.RemoteProtocolError as exc:
            raise PmproxyConnectionError(str(exc)) from exc
        except httpx.TimeoutException as exc:
            raise PmproxyTimeoutError(str(exc)) from exc
        self._raise_for_response(response)
        return response

    async def _post(self, path: str, data: dict | None = None) -> httpx.Response:
        """POST with form-encoded body — mirrors _get but avoids URL length limits."""
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

    # ── Series API (stateless) ──────────────────────────────────────────────

    async def series_sources(self, match: str = "") -> list[dict]:
        """GET /series/sources — list monitored hosts."""
        params: dict = {"match": match or "*"}
        response = await self._get("/series/sources", params)
        return response.json()

    async def series_query(self, expr: str) -> list[str]:
        """GET /series/query — resolve expression to series IDs."""
        response = await self._get("/series/query", {"expr": expr})
        return response.json()

    async def series_values(
        self,
        series: list[str],
        start: str,
        finish: str,
        interval: str | None = None,
        samples: int | None = None,
    ) -> list[dict]:
        """Fetch time-series data points, batching large series lists via POST."""
        extra: dict = {"start": start, "finish": finish}
        if interval:
            extra["interval"] = interval
        if samples is not None:
            extra["samples"] = samples

        if len(series) <= SERIES_BATCH_SIZE:
            params = {"series": ",".join(series), **extra}
            response = await self._get("/series/values", params)
            return response.json()

        results: list[dict] = []
        for i in range(0, len(series), SERIES_BATCH_SIZE):
            chunk = series[i : i + SERIES_BATCH_SIZE]
            data = {"series": ",".join(chunk), **extra}
            response = await self._post("/series/values", data=data)
            results.extend(response.json())
        return results

    async def series_descs(self, series: list[str]) -> list[dict]:
        """GET /series/descs — metric descriptors for series IDs."""
        response = await self._get("/series/descs", {"series": ",".join(series)})
        return response.json()

    async def series_instances(self, series: list[str]) -> list[dict]:
        """Fetch instance domain members, batching large series lists via POST."""
        if len(series) <= SERIES_BATCH_SIZE:
            response = await self._get("/series/instances", {"series": ",".join(series)})
            return response.json()

        results: list[dict] = []
        for i in range(0, len(series), SERIES_BATCH_SIZE):
            chunk = series[i : i + SERIES_BATCH_SIZE]
            response = await self._post("/series/instances", data={"series": ",".join(chunk)})
            results.extend(response.json())
        return results

    async def series_labels(self, series: list[str]) -> list[dict]:
        """Fetch labels for series, batching large series lists via POST."""
        if len(series) <= SERIES_BATCH_SIZE:
            response = await self._get("/series/labels", {"series": ",".join(series)})
            return response.json()

        results: list[dict] = []
        for i in range(0, len(series), SERIES_BATCH_SIZE):
            chunk = series[i : i + SERIES_BATCH_SIZE]
            response = await self._post("/series/labels", data={"series": ",".join(chunk)})
            results.extend(response.json())
        return results

    # ── Search API (stateless) ──────────────────────────────────────────────

    async def search_text(
        self,
        query: str,
        result_type: str = "",
        limit: int = 10,
        offset: int = 0,
    ) -> dict:
        """GET /search/text — full-text search."""
        params: dict = {"query": query, "limit": limit, "offset": offset}
        if result_type and result_type != "all":
            params["type"] = result_type
        response = await self._get("/search/text", params)
        return response.json()

    async def search_suggest(self, query: str, limit: int = 10) -> list[str]:
        """GET /search/suggest — autocomplete."""
        response = await self._get("/search/suggest", {"query": query, "limit": limit})
        return response.json()

    # ── PMAPI (context-based) ───────────────────────────────────────────────

    async def _ensure_context(self, host: str = "") -> int:
        """Get or create a PMAPI context for the given host."""
        cache_key = host or "__default__"
        if cache_key in self._contexts:
            return self._contexts[cache_key]

        params: dict = {"polltimeout": 120}
        if host:
            params["hostspec"] = host

        try:
            response = await self._client.get("/pmapi/context", params=params)
        except httpx.ConnectError as exc:
            raise PmproxyConnectionError(str(exc)) from exc
        except httpx.TimeoutException as exc:
            raise PmproxyTimeoutError(str(exc)) from exc

        if response.status_code not in (200,):
            try:
                message = response.json().get("message", response.text)
            except Exception:
                message = response.text
            raise PmproxyAPIError(response.status_code, message)

        ctx_id: int = response.json()["context"]
        self._contexts[cache_key] = ctx_id
        logger.debug("Created PMAPI context %d for host %r", ctx_id, host)
        return ctx_id

    async def _pmapi_get(self, path: str, params: dict, host: str = "") -> httpx.Response:
        """Make a PMAPI request, handling expired-context retry."""
        ctx_id = await self._ensure_context(host)
        params = {**params, "context": ctx_id}
        try:
            response = await self._client.get(path, params=params)
        except httpx.ConnectError as exc:
            raise PmproxyConnectionError(str(exc)) from exc
        except httpx.TimeoutException as exc:
            raise PmproxyTimeoutError(str(exc)) from exc

        context_expired = response.status_code == 403 or (
            response.status_code == 400 and "unknown context identifier" in response.text.lower()
        )
        if context_expired:
            # Context expired — invalidate and retry once
            cache_key = host or "__default__"
            self._contexts.pop(cache_key, None)
            ctx_id = await self._ensure_context(host)
            params = {**params, "context": ctx_id}
            try:
                response = await self._client.get(path, params=params)
            except httpx.ConnectError as exc:
                raise PmproxyConnectionError(str(exc)) from exc
            except httpx.TimeoutException as exc:
                raise PmproxyTimeoutError(str(exc)) from exc

        self._raise_for_response(response)
        return response

    async def pmapi_metric(self, names: list[str], host: str = "") -> dict:
        """GET /pmapi/metric — metric metadata."""
        params = {"names": ",".join(names)}
        response = await self._pmapi_get("/pmapi/metric", params, host)
        return response.json()

    async def pmapi_fetch(self, names: list[str], host: str = "") -> dict:
        """GET /pmapi/fetch — live metric values."""
        params = {"names": ",".join(names)}
        response = await self._pmapi_get("/pmapi/fetch", params, host)
        return response.json()

    async def pmapi_indom(self, metric_name: str, host: str = "") -> dict:
        """GET /pmapi/indom — instance domain listing."""
        params = {"name": metric_name}
        response = await self._pmapi_get("/pmapi/indom", params, host)
        return response.json()

    async def pmapi_children(self, prefix: str, host: str = "") -> dict:
        """GET /pmapi/children — namespace tree traversal."""
        params = {"prefix": prefix}
        response = await self._pmapi_get("/pmapi/children", params, host)
        return response.json()

    async def pmapi_derive(self, name: str, expr: str, host: str = "") -> dict:
        """GET /pmapi/derive — register derived metric."""
        params = {"name": name, "expr": expr}
        response = await self._pmapi_get("/pmapi/derive", params, host)
        return response.json()

    # ── Health ──────────────────────────────────────────────────────────────

    async def probe(self) -> tuple[bool, str | None]:
        """Lightweight connectivity check — returns (True, None) if pmproxy responds."""
        try:
            response = await self._client.get(
                "/series/sources",
                params={"match": "*"},
                timeout=5.0,
            )
            response.raise_for_status()
            return True, None
        except (PmproxyConnectionError, PmproxyTimeoutError) as exc:
            return False, str(exc)
        except httpx.ConnectError as exc:
            return False, str(exc)
        except httpx.TimeoutException as exc:
            return False, str(exc)
        except httpx.HTTPStatusError as exc:
            return False, str(exc)
