"""Unit tests for _fetch_window batching behaviour."""

from __future__ import annotations

import httpx
import pytest
import respx

from pmmcp.client import PmproxyClient, PmproxyConnectionError
from pmmcp.config import PmproxyConfig

PMPROXY_BASE = "http://localhost:44322"


@pytest.fixture
def config():
    return PmproxyConfig(url=PMPROXY_BASE, timeout=5.0)


# ---------------------------------------------------------------------------
# _chunked helper tests
# ---------------------------------------------------------------------------


def test_chunked_yields_correct_slices():
    """_chunked splits a list into chunks of the given size."""
    from pmmcp.tools._fetch import _chunked

    result = list(_chunked([1, 2, 3, 4, 5], 2))
    assert result == [[1, 2], [3, 4], [5]]


def test_chunked_empty_list():
    from pmmcp.tools._fetch import _chunked

    assert list(_chunked([], 5)) == []


def test_chunked_exact_multiple():
    from pmmcp.tools._fetch import _chunked

    assert list(_chunked([1, 2, 3, 4], 2)) == [[1, 2], [3, 4]]


# ---------------------------------------------------------------------------
# _fetch_window batching tests
# ---------------------------------------------------------------------------

TEST_SERIES = "605fc77742cd0317597291329561ac4e50c0dd12"


# ---------------------------------------------------------------------------
# _fetch_descs tests
# ---------------------------------------------------------------------------


class TestFetchDescs:
    """Tests for _fetch_descs — fetches metric semantics from /series/descs."""

    @respx.mock
    async def test_returns_semantics_mapping(self, config):
        """Happy path: maps series ID to its semantics string."""
        respx.get(f"{PMPROXY_BASE}/series/descs").mock(
            return_value=httpx.Response(
                200,
                json=[{"series": TEST_SERIES, "semantics": "counter"}],
            )
        )

        client = PmproxyClient(config)
        try:
            from pmmcp.tools._fetch import _fetch_descs

            result = await _fetch_descs(client, [TEST_SERIES])
            assert result == {TEST_SERIES: "counter"}
        finally:
            await client.close()

    @respx.mock
    async def test_empty_input_returns_empty(self, config):
        """No series IDs → no pmproxy call, empty dict."""
        from pmmcp.tools._fetch import _fetch_descs

        client = PmproxyClient(config)
        try:
            result = await _fetch_descs(client, [])
            assert result == {}
        finally:
            await client.close()

    @respx.mock
    async def test_pmproxy_error_returns_empty(self, config):
        """On pmproxy HTTP error, swallow and return empty dict."""
        respx.get(f"{PMPROXY_BASE}/series/descs").mock(
            return_value=httpx.Response(500, json={"message": "internal error"})
        )

        client = PmproxyClient(config)
        try:
            from pmmcp.tools._fetch import _fetch_descs

            result = await _fetch_descs(client, [TEST_SERIES])
            assert result == {}
        finally:
            await client.close()

    @respx.mock
    async def test_missing_semantics_defaults_to_instant(self, config):
        """When descs response omits 'semantics', default to 'instant'."""
        respx.get(f"{PMPROXY_BASE}/series/descs").mock(
            return_value=httpx.Response(
                200,
                json=[{"series": TEST_SERIES}],
            )
        )

        client = PmproxyClient(config)
        try:
            from pmmcp.tools._fetch import _fetch_descs

            result = await _fetch_descs(client, [TEST_SERIES])
            assert result == {TEST_SERIES: "instant"}
        finally:
            await client.close()


SERIES_IDS = [f"series{i:04d}" for i in range(25)]


def _make_values(series_id: str, values: list[float], base_ts: float = 1547483646.0) -> list[dict]:
    return [
        {"series": series_id, "timestamp": base_ts + i * 60, "value": str(v)}
        for i, v in enumerate(values)
    ]


@respx.mock
async def test_fetch_window_batches_series_values_calls(config):
    """_fetch_window issues multiple series_values calls when IDs exceed batch size.

    With 25 series IDs and a batch size of 20, we expect exactly 2 calls to
    /series/values — one for IDs 0-19, one for IDs 20-24.
    """
    import pmmcp.tools._fetch as fetch_module

    original_batch_size = fetch_module._SERIES_BATCH_SIZE
    fetch_module._SERIES_BATCH_SIZE = 20

    try:
        respx.get(f"{PMPROXY_BASE}/series/query").mock(
            return_value=httpx.Response(200, json=SERIES_IDS)
        )
        values_route = respx.get(f"{PMPROXY_BASE}/series/values").mock(
            return_value=httpx.Response(200, json=[])
        )
        respx.get(f"{PMPROXY_BASE}/series/labels").mock(return_value=httpx.Response(200, json=[]))
        respx.get(f"{PMPROXY_BASE}/series/instances").mock(
            return_value=httpx.Response(200, json=[])
        )

        from pmmcp.tools._fetch import _fetch_window

        client = PmproxyClient(config)
        try:
            await _fetch_window(
                client,
                exprs=["mem.util.used"],
                start="-60minutes",
                end="now",
                interval="1minute",
                limit=100,
            )
        finally:
            await client.close()

        assert values_route.call_count == 2, (
            f"Expected 2 batched calls to /series/values, got {values_route.call_count}"
        )
    finally:
        fetch_module._SERIES_BATCH_SIZE = original_batch_size


@respx.mock
async def test_fetch_window_single_batch_unchanged(config):
    """_fetch_window makes exactly 1 series_values call when IDs fit in one batch."""
    series_ids = [f"series{i:04d}" for i in range(10)]

    respx.get(f"{PMPROXY_BASE}/series/query").mock(
        return_value=httpx.Response(200, json=series_ids)
    )
    values_route = respx.get(f"{PMPROXY_BASE}/series/values").mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get(f"{PMPROXY_BASE}/series/labels").mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{PMPROXY_BASE}/series/instances").mock(return_value=httpx.Response(200, json=[]))

    from pmmcp.tools._fetch import _fetch_window

    client = PmproxyClient(config)
    try:
        await _fetch_window(
            client,
            exprs=["mem.util.used"],
            start="-60minutes",
            end="now",
            interval="1minute",
            limit=100,
        )
    finally:
        await client.close()

    assert values_route.call_count == 1, (
        f"Expected 1 call for small batch, got {values_route.call_count}"
    )


@respx.mock
async def test_fetch_window_batch_error_propagates(config):
    """_fetch_window raises PmproxyConnectionError when a mid-batch call fails."""
    import pmmcp.tools._fetch as fetch_module

    original_batch_size = fetch_module._SERIES_BATCH_SIZE
    fetch_module._SERIES_BATCH_SIZE = 20

    call_count = 0

    def values_side_effect(request):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise httpx.RemoteProtocolError("Server disconnected", request=request)
        return httpx.Response(200, json=[])

    try:
        respx.get(f"{PMPROXY_BASE}/series/query").mock(
            return_value=httpx.Response(200, json=SERIES_IDS)
        )
        respx.get(f"{PMPROXY_BASE}/series/values").mock(side_effect=values_side_effect)
        respx.get(f"{PMPROXY_BASE}/series/labels").mock(return_value=httpx.Response(200, json=[]))
        respx.get(f"{PMPROXY_BASE}/series/instances").mock(
            return_value=httpx.Response(200, json=[])
        )

        from pmmcp.tools._fetch import _fetch_window

        client = PmproxyClient(config)
        try:
            with pytest.raises(PmproxyConnectionError):
                await _fetch_window(
                    client,
                    exprs=["mem.util.used"],
                    start="-60minutes",
                    end="now",
                    interval="1minute",
                    limit=100,
                )
        finally:
            await client.close()
    finally:
        fetch_module._SERIES_BATCH_SIZE = original_batch_size
