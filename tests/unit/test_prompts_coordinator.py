"""Unit tests for coordinate_investigation prompt — T013-T017."""

from __future__ import annotations

_ALL_SUBSYSTEMS = {"cpu", "memory", "disk", "network", "process", "crosscutting"}


# ---------------------------------------------------------------------------
# T013: _coordinate_investigation_impl — dispatches all 6 subsystems
# ---------------------------------------------------------------------------


def test_coordinator_impl_returns_messages():
    """Coordinator returns list[dict] with role='user'."""
    from pmmcp.prompts.coordinator import _coordinate_investigation_impl

    result = _coordinate_investigation_impl(request="app is slow")
    assert isinstance(result, list)
    assert len(result) >= 1
    assert result[0]["role"] == "user"
    assert len(result[0]["content"]) > 0


def test_coordinator_impl_mentions_all_subsystems():
    """Coordinator content references all 6 subsystems."""
    from pmmcp.prompts.coordinator import _coordinate_investigation_impl

    text = _coordinate_investigation_impl(request="app is slow")[0]["content"]
    for subsystem in _ALL_SUBSYSTEMS:
        assert subsystem in text.lower(), f"Missing subsystem reference: {subsystem}"


def test_coordinator_impl_references_specialist_investigate():
    """Coordinator content references specialist_investigate prompt."""
    from pmmcp.prompts.coordinator import _coordinate_investigation_impl

    text = _coordinate_investigation_impl(request="app is slow")[0]["content"]
    assert "specialist_investigate" in text


# ---------------------------------------------------------------------------
# T014: parallel + sequential dispatch instructions
# ---------------------------------------------------------------------------


def test_coordinator_impl_parallel_and_sequential():
    """Coordinator includes both parallel dispatch and sequential fallback."""
    from pmmcp.prompts.coordinator import _coordinate_investigation_impl

    text = _coordinate_investigation_impl(request="app is slow")[0]["content"]
    assert "parallel" in text.lower(), "Missing parallel dispatch guidance"
    assert "sequential" in text.lower(), "Missing sequential fallback guidance"


# ---------------------------------------------------------------------------
# T015: synthesis / cross-referencing instructions
# ---------------------------------------------------------------------------


def test_coordinator_impl_synthesis_instructions():
    """Coordinator includes cross-referencing and synthesis guidance."""
    from pmmcp.prompts.coordinator import _coordinate_investigation_impl

    text = _coordinate_investigation_impl(request="app is slow")[0]["content"].lower()
    # At least two of: cross-reference, correlat(e|ion), unified, narrative, synthe(sis|size)
    matches = sum(1 for term in ("cross-referenc", "correlat", "synthe") if term in text)
    assert matches >= 2, "Missing cross-referencing / synthesis guidance"


# ---------------------------------------------------------------------------
# T016: partial results / failure handling
# ---------------------------------------------------------------------------


def test_coordinator_impl_partial_results():
    """Coordinator includes guidance for handling partial results / failures."""
    from pmmcp.prompts.coordinator import _coordinate_investigation_impl

    text = _coordinate_investigation_impl(request="app is slow")[0]["content"].lower()
    assert "fail" in text or "partial" in text or "unavailable" in text, (
        "Missing partial-result handling guidance"
    )


# ---------------------------------------------------------------------------
# T017: optional parameter interpolation
# ---------------------------------------------------------------------------


def test_coordinator_impl_interpolates_request():
    """request parameter appears in prompt content."""
    from pmmcp.prompts.coordinator import _coordinate_investigation_impl

    text = _coordinate_investigation_impl(request="database is slow")[0]["content"]
    assert "database is slow" in text


def test_coordinator_impl_interpolates_host():
    """host parameter appears in prompt content."""
    from pmmcp.prompts.coordinator import _coordinate_investigation_impl

    text = _coordinate_investigation_impl(request="issue", host="db01")[0]["content"]
    assert "db01" in text


def test_coordinator_impl_interpolates_time_of_interest():
    """time_of_interest parameter appears in prompt content."""
    from pmmcp.prompts.coordinator import _coordinate_investigation_impl

    text = _coordinate_investigation_impl(request="issue", time_of_interest="yesterday 3pm")[0][
        "content"
    ]
    assert "yesterday 3pm" in text


def test_coordinator_impl_interpolates_lookback():
    """lookback parameter appears in prompt content."""
    from pmmcp.prompts.coordinator import _coordinate_investigation_impl

    text = _coordinate_investigation_impl(request="issue", lookback="6hours")[0]["content"]
    assert "6hours" in text


# ---------------------------------------------------------------------------
# T032-T034: Classification-based ranking in coordinator synthesis
# ---------------------------------------------------------------------------


def test_coordinator_classification_ranking():
    """T032: Coordinator ranks ANOMALY above BASELINE/RECURRING regardless
    of severity, with severity as secondary sort within each tier."""
    from pmmcp.prompts.coordinator import _coordinate_investigation_impl

    text = _coordinate_investigation_impl(request="app is slow")[0]["content"]
    assert "ANOMALY" in text, "Coordinator missing ANOMALY reference"
    has_ranking = any(phrase in text.lower() for phrase in ("rank", "prioriti", "above", "tier"))
    assert has_ranking, "Coordinator missing classification ranking guidance"


def test_coordinator_baseline_callout():
    """T033: Coordinator explicitly calls out findings that are normal
    behaviour for the host."""
    from pmmcp.prompts.coordinator import _coordinate_investigation_impl

    text = _coordinate_investigation_impl(request="app is slow")[0]["content"]
    has_callout = any(
        phrase in text.lower()
        for phrase in (
            "normal behaviour",
            "normal behavior",
            "baseline behaviour",
            "baseline behavior",
            "chronic",
        )
    )
    assert has_callout, "Coordinator missing baseline/normal behaviour callout"


def test_coordinator_recurring_pattern_highlight():
    """T034: Coordinator highlights when an apparent anomaly matches a
    known recurring pattern."""
    from pmmcp.prompts.coordinator import _coordinate_investigation_impl

    text = _coordinate_investigation_impl(request="app is slow")[0]["content"]
    assert "RECURRING" in text or "recurring" in text, (
        "Coordinator missing recurring pattern reference"
    )


# ---------------------------------------------------------------------------
# Phase 3 visualisation tests
# ---------------------------------------------------------------------------


def test_coordinator_phase3_visualisation():
    """Coordinator includes Phase 3 visualisation guidance."""
    from pmmcp.prompts.coordinator import _coordinate_investigation_impl

    text = _coordinate_investigation_impl(request="app is slow")[0]["content"]
    assert "Phase 3" in text or "phase 3" in text.lower(), (
        "Coordinator missing Phase 3"
    )
    assert "dashboard" in text.lower(), (
        "Coordinator Phase 3 must reference dashboard creation"
    )


def test_coordinator_grafana_conventions():
    """Coordinator includes Grafana dashboard conventions from issue #10."""
    from pmmcp.prompts.coordinator import _coordinate_investigation_impl

    text = _coordinate_investigation_impl(request="app is slow")[0]["content"]
    assert "pmmcp-triage" in text, "Missing folder convention"
    assert "pmmcp-generated" in text, "Missing tag convention"
    assert "YYYY-MM-DD" in text, "Missing naming convention"


def test_coordinator_visualisation_fallback_cascade():
    """Coordinator includes fallback cascade (Grafana -> HTML -> text)."""
    from pmmcp.prompts.coordinator import _coordinate_investigation_impl

    text = _coordinate_investigation_impl(request="app is slow")[0]["content"].lower()
    assert "fallback" in text or "unavailable" in text, (
        "Coordinator missing visualisation fallback cascade"
    )


def test_coordinator_deeplink_guidance():
    """Coordinator instructs returning a deeplink after dashboard creation."""
    from pmmcp.prompts.coordinator import _coordinate_investigation_impl

    text = _coordinate_investigation_impl(request="app is slow")[0]["content"].lower()
    assert "deeplink" in text or "deep link" in text or "url" in text, (
        "Coordinator must instruct returning dashboard URL/deeplink"
    )
