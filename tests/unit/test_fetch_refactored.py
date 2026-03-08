"""Tests for refactored _fetch_window, _resolve_series_ids, and _fetch_metadata."""

from __future__ import annotations

import httpx
import pytest
import respx

from pmmcp.client import PmproxyClient
from pmmcp.config import PmproxyConfig

PMPROXY_BASE = "http://localhost:44322"

SERIES_A = "aaaa" * 10  # 40 chars
SERIES_B = "bbbb" * 10
SERIES_C = "cccc" * 10


@pytest.fixture
def config():
    return PmproxyConfig(url=PMPROXY_BASE, timeout=5.0)


# ── _resolve_series_ids ──────────────────────────────────────────────────────


class TestResolveSeriesIds:
    @respx.mock
    async def test_queries_all_expressions(self, config):
        """_resolve_series_ids queries each expression and merges results."""
        from pmmcp.tools._fetch import _resolve_series_ids

        query_route = respx.get(f"{PMPROXY_BASE}/series/query")

        # First expression returns A and B, second returns B and C
        query_route.side_effect = [
            httpx.Response(200, json=[SERIES_A, SERIES_B]),
            httpx.Response(200, json=[SERIES_B, SERIES_C]),
        ]

        client = PmproxyClient(config)
        try:
            ids = await _resolve_series_ids(client, ["expr1", "expr2"])
            assert query_route.call_count == 2
            # Should be deduplicated
            assert set(ids) == {SERIES_A, SERIES_B, SERIES_C}
            assert len(ids) == 3
        finally:
            await client.close()

    @respx.mock
    async def test_handles_dict_return_type(self, config):
        """_resolve_series_ids handles pmproxy returning list of dicts."""
        from pmmcp.tools._fetch import _resolve_series_ids

        respx.get(f"{PMPROXY_BASE}/series/query").mock(
            return_value=httpx.Response(
                200, json=[{"series": SERIES_A}, {"series": SERIES_B}]
            )
        )

        client = PmproxyClient(config)
        try:
            ids = await _resolve_series_ids(client, ["some.metric"])
            assert set(ids) == {SERIES_A, SERIES_B}
        finally:
            await client.close()

    @respx.mock
    async def test_empty_result(self, config):
        """_resolve_series_ids returns empty list when no series found."""
        from pmmcp.tools._fetch import _resolve_series_ids

        respx.get(f"{PMPROXY_BASE}/series/query").mock(
            return_value=httpx.Response(200, json=[])
        )

        client = PmproxyClient(config)
        try:
            ids = await _resolve_series_ids(client, ["nonexistent"])
            assert ids == []
        finally:
            await client.close()


# ── _fetch_metadata ──────────────────────────────────────────────────────────


class TestFetchMetadata:
    @respx.mock
    async def test_fetches_labels_and_instances(self, config):
        """_fetch_metadata returns name_by_series and instance_name_by_series."""
        from pmmcp.tools._fetch import _fetch_metadata

        respx.get(f"{PMPROXY_BASE}/series/labels").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "series": SERIES_A,
                        "labels": {"metric.name": "kernel.all.load"},
                    }
                ],
            )
        )
        respx.get(f"{PMPROXY_BASE}/series/instances").mock(
            return_value=httpx.Response(
                200,
                json=[{"series": SERIES_A, "name": "1 minute"}],
            )
        )

        client = PmproxyClient(config)
        try:
            name_by_series, instance_by_series = await _fetch_metadata(
                client, [SERIES_A]
            )
            assert name_by_series[SERIES_A] == "kernel.all.load"
            assert instance_by_series[SERIES_A] == "1 minute"
        finally:
            await client.close()

    @respx.mock
    async def test_labels_error_returns_empty(self, config):
        """_fetch_metadata returns empty dicts when labels call fails."""
        from pmmcp.tools._fetch import _fetch_metadata

        respx.get(f"{PMPROXY_BASE}/series/labels").mock(
            return_value=httpx.Response(500, text="Internal error")
        )
        respx.get(f"{PMPROXY_BASE}/series/instances").mock(
            return_value=httpx.Response(
                200,
                json=[{"series": SERIES_A, "name": "1 minute"}],
            )
        )

        client = PmproxyClient(config)
        try:
            name_by_series, instance_by_series = await _fetch_metadata(
                client, [SERIES_A]
            )
            # Labels failed, so name_by_series should be empty
            assert name_by_series == {}
            # Instances should still work
            assert instance_by_series[SERIES_A] == "1 minute"
        finally:
            await client.close()


# ── _fetch_window with new signature ─────────────────────────────────────────


class TestFetchWindowRefactored:
    @respx.mock
    async def test_skips_query_when_series_ids_provided(self, config):
        """_fetch_window does not call series_query when series_ids is given."""
        from pmmcp.tools._fetch import _fetch_window

        query_route = respx.get(f"{PMPROXY_BASE}/series/query").mock(
            return_value=httpx.Response(200, json=[])
        )
        respx.get(f"{PMPROXY_BASE}/series/values").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "series": SERIES_A,
                        "timestamp": 1547483646.0,
                        "value": "42.5",
                    }
                ],
            )
        )
        respx.get(f"{PMPROXY_BASE}/series/labels").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "series": SERIES_A,
                        "labels": {"metric.name": "kernel.all.load"},
                    }
                ],
            )
        )
        respx.get(f"{PMPROXY_BASE}/series/instances").mock(
            return_value=httpx.Response(200, json=[])
        )

        client = PmproxyClient(config)
        try:
            numeric_vals, raw_samples = await _fetch_window(
                client,
                exprs=["kernel.all.load"],
                start="-60minutes",
                end="now",
                interval="1minute",
                limit=100,
                series_ids=[SERIES_A],
            )
            # Query should NOT have been called
            assert not query_route.called
            # Should still have fetched values
            assert len(numeric_vals) > 0
        finally:
            await client.close()

    @respx.mock
    async def test_queries_when_no_series_ids(self, config):
        """_fetch_window calls series_query when series_ids is not provided."""
        from pmmcp.tools._fetch import _fetch_window

        query_route = respx.get(f"{PMPROXY_BASE}/series/query").mock(
            return_value=httpx.Response(200, json=[SERIES_A])
        )
        respx.get(f"{PMPROXY_BASE}/series/values").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "series": SERIES_A,
                        "timestamp": 1547483646.0,
                        "value": "10.0",
                    }
                ],
            )
        )
        respx.get(f"{PMPROXY_BASE}/series/labels").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "series": SERIES_A,
                        "labels": {"metric.name": "mem.util.used"},
                    }
                ],
            )
        )
        respx.get(f"{PMPROXY_BASE}/series/instances").mock(
            return_value=httpx.Response(200, json=[])
        )

        client = PmproxyClient(config)
        try:
            numeric_vals, raw_samples = await _fetch_window(
                client,
                exprs=["mem.util.used"],
                start="-60minutes",
                end="now",
                interval="1minute",
                limit=100,
            )
            assert query_route.called
            assert ("mem.util.used", None) in numeric_vals
        finally:
            await client.close()

    @respx.mock
    async def test_empty_series_returns_empty(self, config):
        """_fetch_window returns empty dicts when no series are found."""
        from pmmcp.tools._fetch import _fetch_window

        respx.get(f"{PMPROXY_BASE}/series/query").mock(
            return_value=httpx.Response(200, json=[])
        )

        client = PmproxyClient(config)
        try:
            numeric_vals, raw_samples = await _fetch_window(
                client,
                exprs=["nonexistent.metric"],
                start="-60minutes",
                end="now",
                interval="1minute",
                limit=100,
            )
            assert numeric_vals == {}
            assert raw_samples == {}
        finally:
            await client.close()
