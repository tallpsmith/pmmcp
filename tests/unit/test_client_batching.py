"""Tests for series ID batching in PmproxyClient.

When series lists exceed SERIES_BATCH_SIZE (150), the client should split
into chunks and POST each chunk, merging results. Under the limit, GET
is used as before.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from pmmcp.client import SERIES_BATCH_SIZE, PmproxyClient
from pmmcp.config import PmproxyConfig

PMPROXY_BASE = "http://localhost:44322"


def _make_series_ids(n: int) -> list[str]:
    """Generate n fake 40-char hex series IDs."""
    return [f"{i:040x}" for i in range(n)]


@pytest.fixture
def config():
    return PmproxyConfig(url=PMPROXY_BASE, timeout=5.0)


# ── series_values ────────────────────────────────────────────────────────────


class TestSeriesValuesBatching:
    """series_values batching behaviour."""

    @respx.mock
    async def test_under_limit_uses_get(self, config):
        """When series count <= SERIES_BATCH_SIZE, a single GET is issued."""
        series = _make_series_ids(10)
        get_route = respx.get(f"{PMPROXY_BASE}/series/values").mock(
            return_value=httpx.Response(200, json=[{"series": series[0], "value": "1"}])
        )
        post_route = respx.post(f"{PMPROXY_BASE}/series/values").mock(
            return_value=httpx.Response(200, json=[])
        )

        client = PmproxyClient(config)
        try:
            result = await client.series_values(series, start="-1hours", finish="now")
            assert get_route.called
            assert not post_route.called
            assert len(result) == 1
        finally:
            await client.close()

    @respx.mock
    async def test_over_limit_uses_post_batches(self, config):
        """When series count > SERIES_BATCH_SIZE, multiple POSTs are issued."""
        series = _make_series_ids(SERIES_BATCH_SIZE + 50)
        # Should be 2 batches: 150 + 50

        call_count = 0

        def post_handler(request):
            nonlocal call_count
            call_count += 1
            return httpx.Response(200, json=[{"series": "x", "value": str(call_count)}])

        get_route = respx.get(f"{PMPROXY_BASE}/series/values").mock(
            return_value=httpx.Response(200, json=[])
        )
        respx.post(f"{PMPROXY_BASE}/series/values").mock(side_effect=post_handler)

        client = PmproxyClient(config)
        try:
            result = await client.series_values(series, start="-1hours", finish="now")
            assert not get_route.called
            assert call_count == 2
            # Results from both batches should be merged
            assert len(result) == 2
        finally:
            await client.close()

    @respx.mock
    async def test_exact_limit_uses_get(self, config):
        """Exactly SERIES_BATCH_SIZE series should still use GET."""
        series = _make_series_ids(SERIES_BATCH_SIZE)
        get_route = respx.get(f"{PMPROXY_BASE}/series/values").mock(
            return_value=httpx.Response(200, json=[{"series": "x", "value": "1"}])
        )
        post_route = respx.post(f"{PMPROXY_BASE}/series/values").mock(
            return_value=httpx.Response(200, json=[])
        )

        client = PmproxyClient(config)
        try:
            await client.series_values(series, start="-1hours", finish="now")
            assert get_route.called
            assert not post_route.called
        finally:
            await client.close()


# ── series_labels ────────────────────────────────────────────────────────────


class TestSeriesLabelsBatching:
    """series_labels batching behaviour."""

    @respx.mock
    async def test_under_limit_uses_get(self, config):
        """series_labels under limit uses GET."""
        series = _make_series_ids(10)
        get_route = respx.get(f"{PMPROXY_BASE}/series/labels").mock(
            return_value=httpx.Response(200, json=[{"series": series[0], "labels": {"host": "a"}}])
        )
        post_route = respx.post(f"{PMPROXY_BASE}/series/labels").mock(
            return_value=httpx.Response(200, json=[])
        )

        client = PmproxyClient(config)
        try:
            result = await client.series_labels(series)
            assert get_route.called
            assert not post_route.called
            assert len(result) == 1
        finally:
            await client.close()

    @respx.mock
    async def test_over_limit_batches_and_merges(self, config):
        """series_labels over limit splits into POST batches, merges results."""
        series = _make_series_ids(SERIES_BATCH_SIZE * 2 + 1)
        # Should be 3 batches: 150 + 150 + 1

        call_count = 0

        def post_handler(request):
            nonlocal call_count
            call_count += 1
            return httpx.Response(200, json=[{"series": "x", "labels": {"batch": call_count}}])

        respx.get(f"{PMPROXY_BASE}/series/labels").mock(return_value=httpx.Response(200, json=[]))
        respx.post(f"{PMPROXY_BASE}/series/labels").mock(side_effect=post_handler)

        client = PmproxyClient(config)
        try:
            result = await client.series_labels(series)
            assert call_count == 3
            assert len(result) == 3
        finally:
            await client.close()


# ── series_instances ─────────────────────────────────────────────────────────


class TestSeriesInstancesBatching:
    """series_instances batching behaviour."""

    @respx.mock
    async def test_under_limit_uses_get(self, config):
        """series_instances under limit uses GET."""
        series = _make_series_ids(5)
        get_route = respx.get(f"{PMPROXY_BASE}/series/instances").mock(
            return_value=httpx.Response(200, json=[{"series": series[0], "instance": 1}])
        )
        post_route = respx.post(f"{PMPROXY_BASE}/series/instances").mock(
            return_value=httpx.Response(200, json=[])
        )

        client = PmproxyClient(config)
        try:
            result = await client.series_instances(series)
            assert get_route.called
            assert not post_route.called
            assert len(result) == 1
        finally:
            await client.close()

    @respx.mock
    async def test_over_limit_batches_and_merges(self, config):
        """series_instances over limit splits into POST batches, merges results."""
        series = _make_series_ids(SERIES_BATCH_SIZE + 1)
        # Should be 2 batches: 150 + 1

        call_count = 0

        def post_handler(request):
            nonlocal call_count
            call_count += 1
            return httpx.Response(200, json=[{"series": "x", "instance": call_count}])

        respx.get(f"{PMPROXY_BASE}/series/instances").mock(
            return_value=httpx.Response(200, json=[])
        )
        respx.post(f"{PMPROXY_BASE}/series/instances").mock(side_effect=post_handler)

        client = PmproxyClient(config)
        try:
            result = await client.series_instances(series)
            assert call_count == 2
            assert len(result) == 2
        finally:
            await client.close()
