"""Unit tests for _fleet_health_check_impl (T018).

FR-008: optional timerange, subsystems (default: cpu/memory/disk/network),
        detail_level (default: summary)
FR-009: host-by-subsystem summary table with status indicators
FR-017: missing-tool abort guard
FR-018: no-metrics-found stop guard
FR-019: out-of-retention stop guard
FR-021: no-hosts-found abort guard
"""

from __future__ import annotations

from pmmcp.prompts.health import _fleet_health_check_impl


def test_returns_at_least_one_message():
    """Returns ≥1 message with no arguments (all defaults)."""
    result = _fleet_health_check_impl()
    assert isinstance(result, list)
    assert len(result) >= 1


def test_messages_have_role_and_content():
    """Each message dict has 'role' and 'content' keys."""
    result = _fleet_health_check_impl()
    for msg in result:
        assert "role" in msg
        assert "content" in msg
        assert msg["content"]  # non-empty


def test_default_subsystems_mentioned():
    """FR-008: default subsystems (cpu, memory, disk, network) are referenced."""
    result = _fleet_health_check_impl()
    full_text = " ".join(msg["content"] for msg in result).lower()
    for subsystem in ("cpu", "memory", "disk", "network"):
        assert subsystem in full_text, f"default subsystem '{subsystem}' not mentioned"


def test_custom_subsystems_respected():
    """FR-008: custom subsystems argument scopes the assessment."""
    result = _fleet_health_check_impl(subsystems="cpu,memory")
    full_text = " ".join(msg["content"] for msg in result)
    assert "cpu,memory" in full_text or (
        "cpu" in full_text.lower() and "memory" in full_text.lower()
    )


def test_timerange_interpolated_when_provided():
    """FR-008: timerange argument is interpolated when provided."""
    result = _fleet_health_check_impl(timerange="-4hours")
    full_text = " ".join(msg["content"] for msg in result)
    assert "-4hours" in full_text


def test_no_timerange_string_none_when_omitted():
    """When timerange is None, the word 'None' does not appear in content."""
    result = _fleet_health_check_impl()
    full_text = " ".join(msg["content"] for msg in result)
    assert "None" not in full_text


def test_detail_level_summary_is_default():
    """FR-008: default detail_level is summary (not detailed drill-down)."""
    result = _fleet_health_check_impl()
    full_text = " ".join(msg["content"] for msg in result).lower()
    assert "summary" in full_text


def test_detail_level_detailed_triggers_drilldown():
    """FR-008: detail_level=detailed instructs drill-down on anomalous hosts."""
    result = _fleet_health_check_impl(detail_level="detailed")
    full_text = " ".join(msg["content"] for msg in result).lower()
    assert "detailed" in full_text or "drill" in full_text or "drill-down" in full_text


def test_host_by_subsystem_summary_table_present():
    """FR-009: summary table instruction is present."""
    result = _fleet_health_check_impl()
    full_text = " ".join(msg["content"] for msg in result).lower()
    assert "table" in full_text or "summary table" in full_text or "per-host" in full_text


def test_status_indicators_mentioned():
    """FR-009: status indicators are mentioned (ok/warn/crit or similar)."""
    result = _fleet_health_check_impl()
    full_text = " ".join(msg["content"] for msg in result).lower()
    assert (
        "ok" in full_text
        or "warn" in full_text
        or "crit" in full_text
        or "healthy" in full_text
        or "status" in full_text
        or "indicator" in full_text
    )


def test_no_hosts_found_guard_present():
    """FR-021: no-hosts-found abort guard is present."""
    result = _fleet_health_check_impl()
    full_text = " ".join(msg["content"] for msg in result).lower()
    assert (
        "no hosts" in full_text
        or "no host" in full_text
        or ("hosts" in full_text and ("found" in full_text or "registered" in full_text))
    )


def test_no_hosts_stop_with_config_suggestion():
    """FR-021: no-hosts stop includes suggestion to verify monitoring config."""
    result = _fleet_health_check_impl()
    full_text = " ".join(msg["content"] for msg in result).lower()
    assert (
        "monitor" in full_text
        or "config" in full_text
        or "configuration" in full_text
        or "verify" in full_text
    )


def test_missing_tool_abort_guard_present():
    """FR-017: missing-tool abort guard is present."""
    result = _fleet_health_check_impl()
    full_text = " ".join(msg["content"] for msg in result)
    assert "tool" in full_text.lower() and (
        "missing" in full_text.lower()
        or "unavailable" in full_text.lower()
        or "abort" in full_text.lower()
        or "stop" in full_text.lower()
    )


def test_no_metrics_found_guard_present():
    """FR-018: no-metrics-found stop guard is present."""
    result = _fleet_health_check_impl()
    full_text = " ".join(msg["content"] for msg in result).lower()
    assert "no metrics" in full_text or "metrics found" in full_text


def test_out_of_retention_guard_present():
    """FR-019: out-of-retention stop guard is present."""
    result = _fleet_health_check_impl()
    full_text = " ".join(msg["content"] for msg in result).lower()
    assert "retention" in full_text


def test_host_enumeration_instruction_present():
    """FR-009 + FR-021: prompt instructs host enumeration before proceeding."""
    result = _fleet_health_check_impl()
    full_text = " ".join(msg["content"] for msg in result).lower()
    assert "pcp_get_hosts" in full_text or "enumerate" in full_text or "list hosts" in full_text


def test_discovery_first_instruction_present():
    """FR-013: discovery-first pattern is present."""
    result = _fleet_health_check_impl()
    full_text = " ".join(msg["content"] for msg in result).lower()
    assert "discover" in full_text or "pcp_discover_metrics" in full_text
