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
