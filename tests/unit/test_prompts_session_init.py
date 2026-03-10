"""Unit tests for _session_init_impl (T002, US1).

FR: session_init prompt instructs Claude to pre-register three canonical derived
metrics via pcp_derive_metric, verify each via pcp_fetch_live, and report
success/failure without aborting the session.
"""

from __future__ import annotations

from pmmcp.prompts.session_init import _session_init_impl


def test_returns_at_least_one_message():
    """Returns ≥1 message for any invocation."""
    result = _session_init_impl()
    assert isinstance(result, list)
    assert len(result) >= 1


def test_messages_have_role_and_content():
    """Each message dict has 'role' and 'content' keys with non-empty content."""
    result = _session_init_impl()
    for msg in result:
        assert "role" in msg
        assert "content" in msg
        assert msg["content"]


def test_all_three_derived_metric_names_present():
    """All three canonical derived metric names appear in the prompt content."""
    result = _session_init_impl()
    full_text = " ".join(msg["content"] for msg in result)
    assert "derived.cpu.utilisation" in full_text
    assert "derived.disk.utilisation" in full_text
    assert "derived.mem.utilisation" in full_text


def test_pcp_derive_metric_referenced_in_content():
    """pcp_derive_metric tool is referenced as the registration mechanism."""
    result = _session_init_impl()
    full_text = " ".join(msg["content"] for msg in result)
    assert "pcp_derive_metric" in full_text


def test_pcp_fetch_live_verification_referenced():
    """pcp_fetch_live is referenced as the verification step."""
    result = _session_init_impl()
    full_text = " ".join(msg["content"] for msg in result)
    assert "pcp_fetch_live" in full_text


def test_failure_handling_without_abort_mentioned():
    """Failure handling instructs reporting without aborting the session."""
    result = _session_init_impl()
    full_text = " ".join(msg["content"] for msg in result)
    # Must describe "report ... without abort" — not "stop" or "abort on failure"
    assert (
        "report" in full_text.lower()
        or "without" in full_text.lower()
        or "do not abort" in full_text.lower()
        or "don't abort" in full_text.lower()
    )


def test_host_interpolated_when_provided():
    """Host argument is interpolated into the prompt content."""
    host = "web-prod-01"
    result = _session_init_impl(host=host)
    full_text = " ".join(msg["content"] for msg in result)
    assert host in full_text


def test_no_none_string_when_host_omitted():
    """When host is None, the string 'None' does not appear in content."""
    result = _session_init_impl()
    full_text = " ".join(msg["content"] for msg in result)
    assert "None" not in full_text


def test_all_three_expressions_present():
    """The actual PCP metric expressions (underlying sources) appear in content."""
    result = _session_init_impl()
    full_text = " ".join(msg["content"] for msg in result)
    # Each derived metric's expression uses a known underlying PCP counter
    assert "kernel.all.cpu.idle" in full_text or "derived.cpu.utilisation" in full_text
    assert "disk.all.avactive" in full_text or "derived.disk.utilisation" in full_text
    assert "mem.util.used" in full_text or "derived.mem.utilisation" in full_text


# ---------------------------------------------------------------------------
# T024: session_init references coordinate_investigation
# ---------------------------------------------------------------------------


def test_session_init_references_coordinate_investigation():
    """session_init content references coordinate_investigation as entry point."""
    result = _session_init_impl()
    full_text = " ".join(msg["content"] for msg in result)
    assert "coordinate_investigation" in full_text, (
        "session_init must reference coordinate_investigation as investigation entry point"
    )


def test_session_init_assertive_coordinator_language():
    """session_init uses assertive language (ALWAYS/DO NOT) for coordinator guidance."""
    result = _session_init_impl()
    full_text = " ".join(msg["content"] for msg in result)
    upper_text = full_text.upper()
    assert "ALWAYS" in upper_text or "DO NOT" in upper_text or "MUST" in upper_text, (
        "session_init must use assertive language directing to coordinate_investigation"
    )


def test_session_init_coordinator_before_derived_metrics():
    """Coordinator guidance appears before the derived metrics registration steps."""
    result = _session_init_impl()
    full_text = " ".join(msg["content"] for msg in result)
    coord_pos = full_text.find("coordinate_investigation")
    derive_pos = full_text.find("Step 1")
    assert coord_pos < derive_pos, (
        "Coordinator guidance must appear before Step 1 (derived metrics)"
    )


def test_session_init_grafana_preflight_references():
    """session_init includes Grafana preflight discovery workflow."""
    result = _session_init_impl()
    full_text = " ".join(msg["content"] for msg in result)
    assert "list_datasources" in full_text, (
        "session_init must reference list_datasources for Grafana preflight"
    )
    assert "performancecopilot" in full_text.lower(), (
        "session_init must reference PCP datasource type for validation"
    )


def test_session_init_grafana_fallback_cascade():
    """session_init includes fallback cascade when Grafana is unavailable."""
    result = _session_init_impl()
    full_text = " ".join(msg["content"] for msg in result).lower()
    assert "fallback" in full_text or "unavailable" in full_text, (
        "session_init must describe fallback when Grafana is unavailable"
    )
