"""Unit tests for _compare_periods_impl (T013).

FR-006: required params baseline_start/end, comparison_start/end; optional host, subsystem, context
FR-007: broad scan first, magnitude-ranked results, root-cause hypothesis
FR-017: missing-tool abort guard
FR-019: out-of-retention stop guard
FR-020: overlapping windows → invalid input, stop
"""

from __future__ import annotations

from pmmcp.prompts.compare import _compare_periods_impl

BASELINE = ("-8hours", "-4hours")
COMPARISON = ("-4hours", "now")


def test_returns_at_least_one_message():
    """Returns ≥1 message for valid non-overlapping periods."""
    result = _compare_periods_impl(
        baseline_start=BASELINE[0],
        baseline_end=BASELINE[1],
        comparison_start=COMPARISON[0],
        comparison_end=COMPARISON[1],
    )
    assert isinstance(result, list)
    assert len(result) >= 1


def test_messages_have_role_and_content():
    """Each message dict has 'role' and 'content' keys."""
    result = _compare_periods_impl(
        baseline_start=BASELINE[0],
        baseline_end=BASELINE[1],
        comparison_start=COMPARISON[0],
        comparison_end=COMPARISON[1],
    )
    for msg in result:
        assert "role" in msg
        assert "content" in msg
        assert msg["content"]  # non-empty


def test_baseline_start_interpolated():
    """FR-006: baseline_start is interpolated into content."""
    result = _compare_periods_impl(
        baseline_start="-24hours",
        baseline_end="-12hours",
        comparison_start="-12hours",
        comparison_end="-1hours",
    )
    full_text = " ".join(msg["content"] for msg in result)
    assert "-24hours" in full_text


def test_comparison_end_interpolated():
    """FR-006: comparison_end is interpolated into content."""
    result = _compare_periods_impl(
        baseline_start=BASELINE[0],
        baseline_end=BASELINE[1],
        comparison_start=COMPARISON[0],
        comparison_end="-1hours",
    )
    full_text = " ".join(msg["content"] for msg in result)
    assert "-1hours" in full_text


def test_host_interpolated_when_provided():
    """FR-006: host argument is interpolated when provided."""
    result = _compare_periods_impl(
        baseline_start=BASELINE[0],
        baseline_end=BASELINE[1],
        comparison_start=COMPARISON[0],
        comparison_end=COMPARISON[1],
        host="db-prod-01",
    )
    full_text = " ".join(msg["content"] for msg in result)
    assert "db-prod-01" in full_text


def test_no_host_string_none_when_omitted():
    """When host is None, the word 'None' does not appear in content."""
    result = _compare_periods_impl(
        baseline_start=BASELINE[0],
        baseline_end=BASELINE[1],
        comparison_start=COMPARISON[0],
        comparison_end=COMPARISON[1],
    )
    full_text = " ".join(msg["content"] for msg in result)
    assert "None" not in full_text


def test_subsystem_interpolated_when_provided():
    """FR-006: subsystem argument is interpolated when provided."""
    result = _compare_periods_impl(
        baseline_start=BASELINE[0],
        baseline_end=BASELINE[1],
        comparison_start=COMPARISON[0],
        comparison_end=COMPARISON[1],
        subsystem="disk",
    )
    full_text = " ".join(msg["content"] for msg in result)
    assert "disk" in full_text.lower()


def test_context_interpolated_when_provided():
    """FR-006: context argument is interpolated when provided."""
    context = "deployed v2.3.1 at 14:00"
    result = _compare_periods_impl(
        baseline_start=BASELINE[0],
        baseline_end=BASELINE[1],
        comparison_start=COMPARISON[0],
        comparison_end=COMPARISON[1],
        context=context,
    )
    full_text = " ".join(msg["content"] for msg in result)
    assert context in full_text


def test_broad_scan_first_instruction():
    """FR-007: instructs broad scan first before drilling down."""
    result = _compare_periods_impl(
        baseline_start=BASELINE[0],
        baseline_end=BASELINE[1],
        comparison_start=COMPARISON[0],
        comparison_end=COMPARISON[1],
    )
    full_text = " ".join(msg["content"] for msg in result)
    assert "broad" in full_text.lower() or "scan" in full_text.lower()


def test_magnitude_ranking_instruction():
    """FR-007: instructs ranking by magnitude of change."""
    result = _compare_periods_impl(
        baseline_start=BASELINE[0],
        baseline_end=BASELINE[1],
        comparison_start=COMPARISON[0],
        comparison_end=COMPARISON[1],
    )
    full_text = " ".join(msg["content"] for msg in result)
    assert "magnitude" in full_text.lower() or "rank" in full_text.lower()


def test_root_cause_hypothesis_instruction():
    """FR-007: instructs including a root-cause hypothesis."""
    result = _compare_periods_impl(
        baseline_start=BASELINE[0],
        baseline_end=BASELINE[1],
        comparison_start=COMPARISON[0],
        comparison_end=COMPARISON[1],
    )
    full_text = " ".join(msg["content"] for msg in result)
    assert "root" in full_text.lower() or "hypothesis" in full_text.lower()


def test_missing_tool_abort_guard_present():
    """FR-017: missing-tool abort guard is present."""
    result = _compare_periods_impl(
        baseline_start=BASELINE[0],
        baseline_end=BASELINE[1],
        comparison_start=COMPARISON[0],
        comparison_end=COMPARISON[1],
    )
    full_text = " ".join(msg["content"] for msg in result)
    assert "tool" in full_text.lower() and (
        "missing" in full_text.lower()
        or "unavailable" in full_text.lower()
        or "abort" in full_text.lower()
        or "stop" in full_text.lower()
    )


def test_out_of_retention_guard_present():
    """FR-019: out-of-retention stop guard is present."""
    result = _compare_periods_impl(
        baseline_start=BASELINE[0],
        baseline_end=BASELINE[1],
        comparison_start=COMPARISON[0],
        comparison_end=COMPARISON[1],
    )
    full_text = " ".join(msg["content"] for msg in result)
    assert "retention" in full_text.lower()


def test_overlap_detection_guard_present():
    """FR-020: overlap detection guard is present."""
    result = _compare_periods_impl(
        baseline_start=BASELINE[0],
        baseline_end=BASELINE[1],
        comparison_start=COMPARISON[0],
        comparison_end=COMPARISON[1],
    )
    full_text = " ".join(msg["content"] for msg in result)
    assert "overlap" in full_text.lower()


def test_overlap_stop_behaviour_described():
    """FR-020: prompt instructs agent to stop on overlap with explanation."""
    result = _compare_periods_impl(
        baseline_start=BASELINE[0],
        baseline_end=BASELINE[1],
        comparison_start=COMPARISON[0],
        comparison_end=COMPARISON[1],
    )
    full_text = " ".join(msg["content"] for msg in result)
    # Must mention stopping and unreliable/invalid results on overlap
    assert (
        "stop" in full_text.lower()
        or "invalid" in full_text.lower()
        or "unreliable" in full_text.lower()
    )


def test_discovery_first_instruction_present():
    """FR-013: discovery-first pattern is present."""
    result = _compare_periods_impl(
        baseline_start=BASELINE[0],
        baseline_end=BASELINE[1],
        comparison_start=COMPARISON[0],
        comparison_end=COMPARISON[1],
    )
    full_text = " ".join(msg["content"] for msg in result)
    assert "discover" in full_text.lower() or "pcp_discover_metrics" in full_text
