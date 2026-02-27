"""Unit tests for _investigate_subsystem_impl (T003).

FR-003: discovery-first workflow
FR-004: subsystem-specific namespace hints
FR-005: presentation standards
FR-013: host argument interpolation
FR-014: symptom argument interpolation
FR-017: missing-tool abort guard
FR-018: no-metrics-found stop guard
FR-019: out-of-retention stop guard
"""

from __future__ import annotations

import pytest

from pmmcp.prompts.investigate import _investigate_subsystem_impl

SUBSYSTEMS = ["cpu", "memory", "disk", "network", "process", "general"]


@pytest.mark.parametrize("subsystem", SUBSYSTEMS)
def test_returns_at_least_one_message(subsystem):
    """Returns ≥1 message for every valid subsystem."""
    result = _investigate_subsystem_impl(subsystem=subsystem)
    assert isinstance(result, list)
    assert len(result) >= 1


@pytest.mark.parametrize("subsystem", SUBSYSTEMS)
def test_messages_have_role_and_content(subsystem):
    """Each message dict has 'role' and 'content' keys."""
    result = _investigate_subsystem_impl(subsystem=subsystem)
    for msg in result:
        assert "role" in msg
        assert "content" in msg
        assert msg["content"]  # non-empty


@pytest.mark.parametrize("subsystem", SUBSYSTEMS)
def test_discovery_first_instruction_present(subsystem):
    """FR-003: discovery-first instruction is present in message content."""
    result = _investigate_subsystem_impl(subsystem=subsystem)
    full_text = " ".join(msg["content"] for msg in result)
    assert "discover" in full_text.lower() or "pcp_discover_metrics" in full_text


def test_cpu_namespace_hints():
    """FR-004: cpu subsystem includes kernel namespace hints."""
    result = _investigate_subsystem_impl(subsystem="cpu")
    full_text = " ".join(msg["content"] for msg in result)
    assert "kernel" in full_text.lower()


def test_memory_namespace_hints():
    """FR-004: memory subsystem includes mem namespace hints."""
    result = _investigate_subsystem_impl(subsystem="memory")
    full_text = " ".join(msg["content"] for msg in result)
    assert "mem" in full_text.lower()


def test_disk_namespace_hints():
    """FR-004: disk subsystem includes disk namespace hints."""
    result = _investigate_subsystem_impl(subsystem="disk")
    full_text = " ".join(msg["content"] for msg in result)
    assert "disk" in full_text.lower()


def test_network_namespace_hints():
    """FR-004: network subsystem includes network namespace hints."""
    result = _investigate_subsystem_impl(subsystem="network")
    full_text = " ".join(msg["content"] for msg in result)
    assert "network" in full_text.lower()


def test_process_namespace_hints():
    """FR-004: process subsystem includes proc namespace hints."""
    result = _investigate_subsystem_impl(subsystem="process")
    full_text = " ".join(msg["content"] for msg in result)
    assert "proc" in full_text.lower()


@pytest.mark.parametrize("subsystem", SUBSYSTEMS)
def test_presentation_standard_cpu_percent(subsystem):
    """FR-005: presentation standard — CPU expressed as percentage."""
    result = _investigate_subsystem_impl(subsystem=subsystem)
    full_text = " ".join(msg["content"] for msg in result)
    assert "%" in full_text


@pytest.mark.parametrize("subsystem", SUBSYSTEMS)
def test_presentation_standard_memory_gb(subsystem):
    """FR-005: presentation standard — memory in GB."""
    result = _investigate_subsystem_impl(subsystem=subsystem)
    full_text = " ".join(msg["content"] for msg in result)
    assert "GB" in full_text


@pytest.mark.parametrize("subsystem", SUBSYSTEMS)
def test_presentation_standard_disk_throughput(subsystem):
    """FR-005: presentation standard — disk throughput in MB/s."""
    result = _investigate_subsystem_impl(subsystem=subsystem)
    full_text = " ".join(msg["content"] for msg in result)
    assert "MB/s" in full_text


@pytest.mark.parametrize("subsystem", SUBSYSTEMS)
def test_missing_tool_abort_guard_present(subsystem):
    """FR-017: missing-tool abort guard is present."""
    result = _investigate_subsystem_impl(subsystem=subsystem)
    full_text = " ".join(msg["content"] for msg in result)
    # Must mention stopping if a required tool is unavailable
    assert "tool" in full_text.lower() and (
        "missing" in full_text.lower()
        or "unavailable" in full_text.lower()
        or "abort" in full_text.lower()
        or "stop" in full_text.lower()
    )


@pytest.mark.parametrize("subsystem", SUBSYSTEMS)
def test_no_metrics_found_guard_present(subsystem):
    """FR-018: no-metrics-found stop guard is present."""
    result = _investigate_subsystem_impl(subsystem=subsystem)
    full_text = " ".join(msg["content"] for msg in result)
    assert "no metrics" in full_text.lower() or "metrics found" in full_text.lower()


@pytest.mark.parametrize("subsystem", SUBSYSTEMS)
def test_out_of_retention_guard_present(subsystem):
    """FR-019: out-of-retention stop guard is present."""
    result = _investigate_subsystem_impl(subsystem=subsystem)
    full_text = " ".join(msg["content"] for msg in result)
    assert "retention" in full_text.lower()


def test_host_interpolated_when_provided():
    """FR-013: host argument is interpolated into message content."""
    host = "web-prod-01"
    result = _investigate_subsystem_impl(subsystem="cpu", host=host)
    full_text = " ".join(msg["content"] for msg in result)
    assert host in full_text


def test_symptom_interpolated_when_provided():
    """FR-014: symptom argument is interpolated into message content."""
    symptom = "high load average after deployment"
    result = _investigate_subsystem_impl(subsystem="cpu", symptom=symptom)
    full_text = " ".join(msg["content"] for msg in result)
    assert symptom in full_text


def test_no_host_when_not_provided():
    """When host is None the word 'None' does not appear in content."""
    result = _investigate_subsystem_impl(subsystem="cpu")
    full_text = " ".join(msg["content"] for msg in result)
    assert "None" not in full_text


def test_timerange_interpolated_when_provided():
    """timerange argument is interpolated into message content."""
    result = _investigate_subsystem_impl(subsystem="cpu", timerange="-2hours")
    full_text = " ".join(msg["content"] for msg in result)
    assert "-2hours" in full_text
