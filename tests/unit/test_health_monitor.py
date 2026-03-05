"""Tests for the periodic health monitor background task."""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

PMPROXY_URL = "http://localhost:44322"


def _make_mock_client(probe_result: tuple[bool, str | None]):
    client = MagicMock()
    client._config.url = PMPROXY_URL
    client.probe = AsyncMock(return_value=probe_result)
    return client


def _make_mock_config(health_interval: int = 15):
    config = MagicMock()
    config.url = PMPROXY_URL
    config.health_interval = health_interval
    return config


async def test_health_monitor_logs_info_when_healthy(caplog):
    """Logs INFO when pmproxy probe succeeds."""
    from pmmcp.server import _health_monitor

    client = _make_mock_client((True, None))
    config = _make_mock_config(health_interval=999)

    # Run one iteration then cancel
    task = asyncio.create_task(_health_monitor(client, config))
    await asyncio.sleep(0.05)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    records = [r for r in caplog.records if "pmmcp.health" in r.name]
    assert any(r.levelno == logging.INFO for r in records)
    assert any("healthy" in r.message.lower() for r in records)


async def test_health_monitor_logs_warning_when_unhealthy(caplog):
    """Logs WARNING when pmproxy probe fails."""
    from pmmcp.server import _health_monitor

    client = _make_mock_client((False, "Connection refused"))
    config = _make_mock_config(health_interval=999)

    task = asyncio.create_task(_health_monitor(client, config))
    await asyncio.sleep(0.05)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    records = [r for r in caplog.records if "pmmcp.health" in r.name]
    assert any(r.levelno == logging.WARNING for r in records)
    assert any("unreachable" in r.message.lower() for r in records)


async def test_health_monitor_includes_url_in_log(caplog):
    """Log messages include the pmproxy URL."""
    from pmmcp.server import _health_monitor

    client = _make_mock_client((True, None))
    config = _make_mock_config(health_interval=999)

    task = asyncio.create_task(_health_monitor(client, config))
    await asyncio.sleep(0.05)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    records = [r for r in caplog.records if "pmmcp.health" in r.name]
    assert any(PMPROXY_URL in r.message for r in records)


async def test_health_monitor_cancels_cleanly():
    """Task cancellation does not raise unhandled exceptions."""
    from pmmcp.server import _health_monitor

    client = _make_mock_client((True, None))
    config = _make_mock_config(health_interval=999)

    task = asyncio.create_task(_health_monitor(client, config))
    await asyncio.sleep(0.01)
    task.cancel()
    # Should raise CancelledError only, not anything unexpected
    with pytest.raises(asyncio.CancelledError):
        await task


async def test_health_monitor_probes_repeatedly():
    """Monitor calls probe more than once over multiple intervals."""
    from pmmcp.server import _health_monitor

    client = _make_mock_client((True, None))
    config = _make_mock_config(health_interval=0)  # zero delay between probes

    task = asyncio.create_task(_health_monitor(client, config))
    await asyncio.sleep(0.05)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert client.probe.call_count >= 2
