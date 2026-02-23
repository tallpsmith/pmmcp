"""Shared test fixtures for pmmcp tests."""

from __future__ import annotations

import httpx
import pytest
import respx

from pmmcp.client import PmproxyClient
from pmmcp.config import PmproxyConfig

PMPROXY_BASE = "http://localhost:44322"

TEST_SOURCE = "2cd6a38f9339f2dd1f0b4775bda89a9e7244def6"
TEST_SERIES = "605fc77742cd0317597291329561ac4e50c0dd12"
TEST_CONTEXT = 348734


@pytest.fixture
def pmproxy_config() -> PmproxyConfig:
    return PmproxyConfig(url=PMPROXY_BASE, timeout=5.0)


@pytest.fixture
async def pmproxy_client(pmproxy_config: PmproxyConfig) -> PmproxyClient:
    client = PmproxyClient(pmproxy_config)
    yield client
    await client.close()


# ── Series endpoint fixtures ───────────────────────────────────────────────


@pytest.fixture
def mock_series_sources():
    with respx.mock(base_url=PMPROXY_BASE, assert_all_called=False) as mock:
        mock.get("/series/sources").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "source": TEST_SOURCE,
                        "context": ["www.acme.com", "acme.internal"],
                    }
                ],
            )
        )
        yield mock


@pytest.fixture
def mock_series_query():
    with respx.mock(base_url=PMPROXY_BASE, assert_all_called=False) as mock:
        mock.get("/series/query").mock(return_value=httpx.Response(200, json=[TEST_SERIES]))
        yield mock


@pytest.fixture
def mock_series_values():
    with respx.mock(base_url=PMPROXY_BASE, assert_all_called=False) as mock:
        mock.get("/series/values").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "series": TEST_SERIES,
                        "timestamp": 1547483646.2147431,
                        "value": "42.5",
                    }
                ],
            )
        )
        yield mock


@pytest.fixture
def mock_series_labels():
    with respx.mock(base_url=PMPROXY_BASE, assert_all_called=False) as mock:
        mock.get("/series/labels").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "series": TEST_SOURCE,
                        "labels": {"hostname": "www.acme.com", "agent": "linux"},
                    }
                ],
            )
        )
        yield mock


# ── PMAPI endpoint fixtures ────────────────────────────────────────────────


@pytest.fixture
def mock_pmapi_context():
    with respx.mock(base_url=PMPROXY_BASE, assert_all_called=False) as mock:
        mock.get("/pmapi/context").mock(
            return_value=httpx.Response(
                200,
                json={
                    "context": TEST_CONTEXT,
                    "source": TEST_SOURCE,
                    "hostspec": "localhost",
                    "labels": {"hostname": "localhost"},
                },
            )
        )
        yield mock


@pytest.fixture
def mock_pmapi_fetch():
    with respx.mock(base_url=PMPROXY_BASE, assert_all_called=False) as mock:
        mock.get("/pmapi/context").mock(
            return_value=httpx.Response(
                200, json={"context": TEST_CONTEXT, "hostspec": "localhost", "labels": {}}
            )
        )
        mock.get("/pmapi/fetch").mock(
            return_value=httpx.Response(
                200,
                json={
                    "context": TEST_CONTEXT,
                    "timestamp": 1547483646.2147431,
                    "values": [
                        {
                            "pmid": "60.0.4",
                            "name": "kernel.all.load",
                            "instances": [
                                {"instance": 1, "value": 0.1},
                                {"instance": 5, "value": 0.25},
                                {"instance": 15, "value": 0.17},
                            ],
                        }
                    ],
                },
            )
        )
        yield mock


@pytest.fixture
def mock_pmapi_metric():
    with respx.mock(base_url=PMPROXY_BASE, assert_all_called=False) as mock:
        mock.get("/pmapi/context").mock(
            return_value=httpx.Response(
                200, json={"context": TEST_CONTEXT, "hostspec": "localhost", "labels": {}}
            )
        )
        mock.get("/pmapi/metric").mock(
            return_value=httpx.Response(
                200,
                json={
                    "context": TEST_CONTEXT,
                    "metrics": [
                        {
                            "name": "kernel.all.load",
                            "pmid": "60.2.0",
                            "indom": "60.2",
                            "type": "FLOAT",
                            "sem": "instant",
                            "units": "none",
                            "series": TEST_SERIES,
                            "source": TEST_SOURCE,
                            "labels": {"hostname": "localhost"},
                            "text-oneline": "1, 5 and 15 minute load average",
                            "text-help": "Extended help text",
                        }
                    ],
                },
            )
        )
        yield mock


@pytest.fixture
def mock_pmapi_indom():
    with respx.mock(base_url=PMPROXY_BASE, assert_all_called=False) as mock:
        mock.get("/pmapi/context").mock(
            return_value=httpx.Response(
                200, json={"context": TEST_CONTEXT, "hostspec": "localhost", "labels": {}}
            )
        )
        mock.get("/pmapi/indom").mock(
            return_value=httpx.Response(
                200,
                json={
                    "context": TEST_CONTEXT,
                    "indom": "60.2",
                    "labels": {"hostname": "localhost"},
                    "instances": [
                        {"instance": 1, "name": "1 minute", "labels": {}},
                        {"instance": 5, "name": "5 minute", "labels": {}},
                        {"instance": 15, "name": "15 minute", "labels": {}},
                    ],
                },
            )
        )
        yield mock


@pytest.fixture
def mock_pmapi_children():
    with respx.mock(base_url=PMPROXY_BASE, assert_all_called=False) as mock:
        mock.get("/pmapi/context").mock(
            return_value=httpx.Response(
                200, json={"context": TEST_CONTEXT, "hostspec": "localhost", "labels": {}}
            )
        )
        mock.get("/pmapi/children").mock(
            return_value=httpx.Response(
                200,
                json={
                    "context": TEST_CONTEXT,
                    "name": "mem",
                    "leaf": ["physmem", "freemem"],
                    "nonleaf": ["util", "numa", "vmstat"],
                },
            )
        )
        yield mock


@pytest.fixture
def mock_pmapi_derive():
    with respx.mock(base_url=PMPROXY_BASE, assert_all_called=False) as mock:
        mock.get("/pmapi/context").mock(
            return_value=httpx.Response(
                200, json={"context": TEST_CONTEXT, "hostspec": "localhost", "labels": {}}
            )
        )
        mock.get("/pmapi/derive").mock(
            return_value=httpx.Response(200, json={"context": TEST_CONTEXT, "success": True})
        )
        yield mock


@pytest.fixture
def mock_search_text():
    with respx.mock(base_url=PMPROXY_BASE, assert_all_called=False) as mock:
        mock.get("/search/text").mock(
            return_value=httpx.Response(
                200,
                json={
                    "total": 1,
                    "elapsed": 0.001,
                    "offset": 0,
                    "limit": 10,
                    "results": [
                        {
                            "name": "kernel.all.load",
                            "type": "metric",
                            "oneline": "1, 5 and 15 minute load average",
                            "helptext": "Extended help text",
                        }
                    ],
                },
            )
        )
        yield mock
