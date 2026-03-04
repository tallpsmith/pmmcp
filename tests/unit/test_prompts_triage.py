"""Unit tests for _incident_triage_impl (T009).

FR-010: symptom required, no severity parameter, default one-hour lookback
FR-011: symptom-to-subsystem mapping guidance
FR-012: host-specific vs fleet-wide scope confirmation
FR-017: missing-tool abort guard
FR-019: out-of-retention stop guard
FR-022: unmappable symptom → fall back to general sweep
"""

from __future__ import annotations

from pmmcp.prompts.triage import _incident_triage_impl


def test_returns_at_least_one_message():
    """Returns ≥1 message for any symptom."""
    result = _incident_triage_impl(symptom="high CPU load")
    assert isinstance(result, list)
    assert len(result) >= 1


def test_messages_have_role_and_content():
    """Each message dict has 'role' and 'content' keys."""
    result = _incident_triage_impl(symptom="disk I/O spikes")
    for msg in result:
        assert "role" in msg
        assert "content" in msg
        assert msg["content"]  # non-empty


def test_symptom_interpolated_in_content():
    """FR-010: symptom argument is interpolated into message content."""
    symptom = "API response times doubled after deploy"
    result = _incident_triage_impl(symptom=symptom)
    full_text = " ".join(msg["content"] for msg in result)
    assert symptom in full_text


def test_host_interpolated_when_provided():
    """FR-010/FR-012: host argument is interpolated when provided."""
    host = "api-prod-03"
    result = _incident_triage_impl(symptom="high load", host=host)
    full_text = " ".join(msg["content"] for msg in result)
    assert host in full_text


def test_no_host_string_none_when_omitted():
    """When host is None, the word 'None' does not appear in content."""
    result = _incident_triage_impl(symptom="memory pressure")
    full_text = " ".join(msg["content"] for msg in result)
    assert "None" not in full_text


def test_timerange_interpolated_when_provided():
    """FR-010: timerange argument is interpolated when provided."""
    result = _incident_triage_impl(symptom="network errors", timerange="-2hours")
    full_text = " ".join(msg["content"] for msg in result)
    assert "-2hours" in full_text


def test_no_severity_parameter():
    """FR-010: no severity parameter — function signature must not accept severity."""
    import inspect

    sig = inspect.signature(_incident_triage_impl)
    assert "severity" not in sig.parameters, "severity parameter must not exist (FR-010)"


def test_symptom_to_subsystem_mapping_guidance_present():
    """FR-011: symptom-to-subsystem mapping guidance is present."""
    result = _incident_triage_impl(symptom="slow database queries")
    full_text = " ".join(msg["content"] for msg in result)
    # Must mention mapping/interpreting symptoms to subsystems
    assert (
        "subsystem" in full_text.lower()
        or "cpu" in full_text.lower()
        or "memory" in full_text.lower()
        or "disk" in full_text.lower()
        or "network" in full_text.lower()
    )


def test_mapping_table_covers_known_symptoms():
    """FR-011: mapping guidance covers multiple common symptom categories."""
    result = _incident_triage_impl(symptom="API latency spiked")
    full_text = " ".join(msg["content"] for msg in result)
    # Should reference CPU, disk/io, network as likely culprits for latency
    subsystems_mentioned = sum(
        1 for s in ("cpu", "disk", "network", "memory", "process") if s in full_text.lower()
    )
    assert subsystems_mentioned >= 3, "mapping guidance should mention ≥3 subsystems"


def test_scope_confirmation_host_vs_fleet():
    """FR-012: instructs agent to confirm host-specific vs fleet-wide scope."""
    result = _incident_triage_impl(symptom="high load")
    full_text = " ".join(msg["content"] for msg in result)
    assert (
        "fleet" in full_text.lower()
        or "fleet-wide" in full_text.lower()
        or "host-specific" in full_text.lower()
        or "all hosts" in full_text.lower()
        or "other hosts" in full_text.lower()
    )


def test_missing_tool_abort_guard_present():
    """FR-017: missing-tool abort guard is present."""
    result = _incident_triage_impl(symptom="system overload")
    full_text = " ".join(msg["content"] for msg in result)
    assert "tool" in full_text.lower() and (
        "missing" in full_text.lower()
        or "unavailable" in full_text.lower()
        or "abort" in full_text.lower()
        or "stop" in full_text.lower()
    )


def test_out_of_retention_guard_present():
    """FR-019: out-of-retention stop guard is present."""
    result = _incident_triage_impl(symptom="intermittent errors")
    full_text = " ".join(msg["content"] for msg in result)
    assert "retention" in full_text.lower()


def test_unmappable_symptom_fallback_to_general():
    """FR-022: unmappable symptom → instructs fall back to general sweep."""
    result = _incident_triage_impl(symptom="gremlins in the system")
    full_text = " ".join(msg["content"] for msg in result)
    assert (
        "general" in full_text.lower()
        or "broad" in full_text.lower()
        or "sweep" in full_text.lower()
        or "fall back" in full_text.lower()
        or "fallback" in full_text.lower()
        or "ambiguous" in full_text.lower()
    )


def test_discovery_first_instruction_present():
    """FR-013: discovery-first pattern is present."""
    result = _incident_triage_impl(symptom="memory leak suspected")
    full_text = " ".join(msg["content"] for msg in result)
    assert "discover" in full_text.lower() or "pcp_discover_metrics" in full_text


# ---------------------------------------------------------------------------
# US2: Explicit 4-step investigation sequence (T007)
# These tests describe the rewritten prompt — MUST FAIL before implementation.
# ---------------------------------------------------------------------------


def test_four_step_sequence_present():
    """All four investigation tools are named in the triage content."""
    result = _incident_triage_impl(symptom="high CPU load")
    full_text = " ".join(msg["content"] for msg in result)
    assert "pcp_detect_anomalies" in full_text, "Step 1 tool missing"
    assert "pcp_compare_windows" in full_text, "Step 2 tool missing"
    assert "pcp_scan_changes" in full_text, "Step 3 tool missing"
    assert "pcp_fetch_timeseries" in full_text, "Step 4 tool missing"


def test_anomaly_detection_is_first_step():
    """pcp_detect_anomalies is named as Step 1 of the investigation sequence."""
    result = _incident_triage_impl(symptom="high CPU load")
    full_text = " ".join(msg["content"] for msg in result)
    step1_pos = full_text.find("Step 1")
    step2_pos = full_text.find("Step 2")
    anomaly_pos = full_text.find("pcp_detect_anomalies")
    assert step1_pos != -1, "Step 1 marker missing"
    assert anomaly_pos != -1, "pcp_detect_anomalies missing"
    assert step1_pos < anomaly_pos < step2_pos, (
        "pcp_detect_anomalies should appear between Step 1 and Step 2 markers"
    )


def test_window_comparison_is_second_step():
    """pcp_compare_windows is named as Step 2 of the investigation sequence."""
    result = _incident_triage_impl(symptom="high CPU load")
    full_text = " ".join(msg["content"] for msg in result)
    step2_pos = full_text.find("Step 2")
    step3_pos = full_text.find("Step 3")
    compare_pos = full_text.find("pcp_compare_windows")
    assert step2_pos != -1, "Step 2 marker missing"
    assert compare_pos != -1, "pcp_compare_windows missing"
    assert step2_pos < compare_pos < step3_pos, (
        "pcp_compare_windows should appear between Step 2 and Step 3 markers"
    )


def test_scan_changes_is_third_step():
    """pcp_scan_changes is named as Step 3 of the investigation sequence."""
    result = _incident_triage_impl(symptom="high CPU load")
    full_text = " ".join(msg["content"] for msg in result)
    step3_pos = full_text.find("Step 3")
    step4_pos = full_text.find("Step 4")
    scan_pos = full_text.find("pcp_scan_changes")
    assert step3_pos != -1, "Step 3 marker missing"
    assert scan_pos != -1, "pcp_scan_changes missing"
    assert step3_pos < scan_pos < step4_pos, (
        "pcp_scan_changes should appear between Step 3 and Step 4 markers"
    )


def test_targeted_drilldown_is_fourth_step():
    """pcp_fetch_timeseries is named as Step 4 (targeted drilldown)."""
    result = _incident_triage_impl(symptom="high CPU load")
    full_text = " ".join(msg["content"] for msg in result)
    step4_pos = full_text.find("Step 4")
    ts_pos = full_text.find("pcp_fetch_timeseries", step4_pos)
    assert step4_pos != -1, "Step 4 marker missing"
    assert ts_pos != -1, "pcp_fetch_timeseries not found after Step 4 marker"


def test_step_transitions_use_qualitative_language():
    """Step transitions use qualitative criteria, not numeric thresholds.

    Requires the 4-step sequence to be present — fails if sequence is absent.
    """
    result = _incident_triage_impl(symptom="high CPU load")
    full_text = " ".join(msg["content"] for msg in result)
    # Prerequisite: the 4-step sequence must be in place
    assert "pcp_compare_windows" in full_text, (
        "4-step sequence must be present to validate transition language"
    )
    # Transitions must be qualitative ("if anomalies found"), not numeric thresholds
    assert "if anomal" in full_text.lower() or "when anomal" in full_text.lower(), (
        "Step transitions should use qualitative language e.g. 'if anomalies found'"
    )
