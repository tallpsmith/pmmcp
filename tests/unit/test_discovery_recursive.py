"""Tests for recursive namespace traversal in _discover_metrics_impl."""

from __future__ import annotations

import httpx
import pytest
import respx

from pmmcp.client import PmproxyClient
from pmmcp.config import PmproxyConfig
from pmmcp.tools.discovery import _discover_metrics_impl

PMPROXY_BASE = "http://localhost:44322"
TEST_CONTEXT = 348734


@pytest.fixture
def config():
    return PmproxyConfig(url=PMPROXY_BASE, timeout=5.0)


def _mock_context():
    return httpx.Response(
        200, json={"context": TEST_CONTEXT, "hostspec": "localhost", "labels": {}}
    )


def _children_handler_kernel(request):
    """Route /pmapi/children based on prefix param for kernel namespace tree.

    kernel (nonleaf: all, percpu)
      kernel.all (leaf: load, nonleaf: cpu)
        kernel.all.cpu (leaf: user, sys, idle)
      kernel.percpu (leaf: interrupts)
    """
    prefix = dict(request.url.params).get("prefix", "")
    if prefix == "kernel":
        return httpx.Response(
            200,
            json={
                "context": TEST_CONTEXT,
                "name": "kernel",
                "leaf": [],
                "nonleaf": ["all", "percpu"],
            },
        )
    elif prefix == "kernel.all":
        return httpx.Response(
            200,
            json={
                "context": TEST_CONTEXT,
                "name": "kernel.all",
                "leaf": ["load"],
                "nonleaf": ["cpu"],
            },
        )
    elif prefix == "kernel.all.cpu":
        return httpx.Response(
            200,
            json={
                "context": TEST_CONTEXT,
                "name": "kernel.all.cpu",
                "leaf": ["user", "sys", "idle"],
                "nonleaf": [],
            },
        )
    elif prefix == "kernel.percpu":
        return httpx.Response(
            200,
            json={
                "context": TEST_CONTEXT,
                "name": "kernel.percpu",
                "leaf": ["interrupts"],
                "nonleaf": [],
            },
        )
    return httpx.Response(404, json={"message": f"Unknown metric: {prefix}"})


@respx.mock
async def test_recurses_nonleaf_children_to_find_leaves(config):
    """Broad prefix like 'kernel' with no direct leaves recurses to find leaf metrics."""
    respx.get(f"{PMPROXY_BASE}/pmapi/context").mock(return_value=_mock_context())
    respx.get(f"{PMPROXY_BASE}/pmapi/children").mock(side_effect=_children_handler_kernel)

    client = PmproxyClient(config)
    try:
        result = await _discover_metrics_impl(
            client, host="", prefix="kernel", search="", limit=50, offset=0
        )
        assert not result.get("isError"), f"Got error: {result}"

        names = sorted(item["name"] for item in result["items"])
        assert names == [
            "kernel.all.cpu.idle",
            "kernel.all.cpu.sys",
            "kernel.all.cpu.user",
            "kernel.all.load",
            "kernel.percpu.interrupts",
        ]
        assert result["total"] == 5
    finally:
        await client.close()


@respx.mock
async def test_all_returned_items_are_leaves(config):
    """Every item in the result must have leaf=True -- no namespace nodes."""
    respx.get(f"{PMPROXY_BASE}/pmapi/context").mock(return_value=_mock_context())
    respx.get(f"{PMPROXY_BASE}/pmapi/children").mock(side_effect=_children_handler_kernel)

    client = PmproxyClient(config)
    try:
        result = await _discover_metrics_impl(
            client, host="", prefix="kernel", search="", limit=50, offset=0
        )
        assert not result.get("isError"), f"Got error: {result}"
        for item in result["items"]:
            assert item["leaf"] is True, f"Non-leaf item in results: {item}"
    finally:
        await client.close()


@respx.mock
async def test_respects_limit_during_recursion(config):
    """When many leaves exist, only returns up to limit."""
    respx.get(f"{PMPROXY_BASE}/pmapi/context").mock(return_value=_mock_context())
    respx.get(f"{PMPROXY_BASE}/pmapi/children").mock(side_effect=_children_handler_kernel)

    client = PmproxyClient(config)
    try:
        result = await _discover_metrics_impl(
            client, host="", prefix="kernel", search="", limit=2, offset=0
        )
        assert not result.get("isError"), f"Got error: {result}"
        assert len(result["items"]) == 2
        assert result["has_more"] is True
        # total should reflect all discovered leaves, not just the page
        assert result["total"] >= 2
    finally:
        await client.close()


@respx.mock
async def test_shallow_when_prefix_has_direct_leaves(config):
    """Prefix that already has leaf children returns them directly."""
    respx.get(f"{PMPROXY_BASE}/pmapi/context").mock(return_value=_mock_context())
    respx.get(f"{PMPROXY_BASE}/pmapi/children").mock(side_effect=_children_handler_kernel)

    client = PmproxyClient(config)
    try:
        result = await _discover_metrics_impl(
            client, host="", prefix="kernel.all.cpu", search="", limit=50, offset=0
        )
        assert not result.get("isError"), f"Got error: {result}"
        names = sorted(item["name"] for item in result["items"])
        assert names == [
            "kernel.all.cpu.idle",
            "kernel.all.cpu.sys",
            "kernel.all.cpu.user",
        ]
    finally:
        await client.close()


@respx.mock
async def test_offset_paginates_recursive_results(config):
    """Offset skips the first N leaves from recursive traversal."""
    respx.get(f"{PMPROXY_BASE}/pmapi/context").mock(return_value=_mock_context())
    respx.get(f"{PMPROXY_BASE}/pmapi/children").mock(side_effect=_children_handler_kernel)

    client = PmproxyClient(config)
    try:
        # Get all 5 leaves, then page with offset=3, limit=10
        result = await _discover_metrics_impl(
            client, host="", prefix="kernel", search="", limit=10, offset=3
        )
        assert not result.get("isError"), f"Got error: {result}"
        assert len(result["items"]) == 2  # 5 total - 3 skipped = 2 remaining
        assert result["total"] == 5
        assert result["has_more"] is False
    finally:
        await client.close()


@respx.mock
async def test_handles_subtree_error_gracefully(config):
    """If a subtree call fails, other subtrees still return results."""

    def handler_with_error(request):
        prefix = dict(request.url.params).get("prefix", "")
        if prefix == "kernel":
            return httpx.Response(
                200,
                json={
                    "context": TEST_CONTEXT,
                    "name": "kernel",
                    "leaf": [],
                    "nonleaf": ["all", "broken"],
                },
            )
        elif prefix == "kernel.all":
            return httpx.Response(
                200,
                json={
                    "context": TEST_CONTEXT,
                    "name": "kernel.all",
                    "leaf": ["load"],
                    "nonleaf": [],
                },
            )
        elif prefix == "kernel.broken":
            return httpx.Response(404, json={"message": "Not found"})
        return httpx.Response(404, json={"message": f"Unknown: {prefix}"})

    respx.get(f"{PMPROXY_BASE}/pmapi/context").mock(return_value=_mock_context())
    respx.get(f"{PMPROXY_BASE}/pmapi/children").mock(side_effect=handler_with_error)

    client = PmproxyClient(config)
    try:
        result = await _discover_metrics_impl(
            client, host="", prefix="kernel", search="", limit=50, offset=0
        )
        assert not result.get("isError"), f"Got error: {result}"
        names = [item["name"] for item in result["items"]]
        assert "kernel.all.load" in names
    finally:
        await client.close()
