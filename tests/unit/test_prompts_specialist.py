"""Unit tests for specialist_investigate prompt — T003, T006-T009."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# T003: _SPECIALIST_KNOWLEDGE structure validation
# ---------------------------------------------------------------------------

_EXPECTED_SUBSYSTEMS = {"cpu", "memory", "disk", "network", "process", "crosscutting"}
_REQUIRED_FIELDS = {"prefix", "display_name", "domain_knowledge", "report_guidance"}


def test_specialist_knowledge_has_all_subsystem_keys():
    """All 6 subsystem keys exist in _SPECIALIST_KNOWLEDGE."""
    from pmmcp.prompts.specialist import _SPECIALIST_KNOWLEDGE

    assert set(_SPECIALIST_KNOWLEDGE.keys()) == _EXPECTED_SUBSYSTEMS


def test_specialist_knowledge_entries_have_required_fields():
    """Each entry has prefix, display_name, domain_knowledge, report_guidance."""
    from pmmcp.prompts.specialist import _SPECIALIST_KNOWLEDGE

    for subsystem, entry in _SPECIALIST_KNOWLEDGE.items():
        for field in _REQUIRED_FIELDS:
            assert field in entry, f"{subsystem} missing field '{field}'"


def test_specialist_knowledge_domain_knowledge_depth():
    """Each domain_knowledge contains >= 5 investigation heuristics (lines)."""
    from pmmcp.prompts.specialist import _SPECIALIST_KNOWLEDGE

    for subsystem, entry in _SPECIALIST_KNOWLEDGE.items():
        dk = entry["domain_knowledge"]
        # Count non-empty lines that look like heuristics (numbered or bulleted)
        heuristic_lines = [
            line
            for line in dk.strip().splitlines()
            if line.strip() and (line.strip()[0].isdigit() or line.strip().startswith("-"))
        ]
        assert len(heuristic_lines) >= 5, (
            f"{subsystem}: expected >= 5 heuristics, got {len(heuristic_lines)}"
        )


def test_specialist_knowledge_prefix_types():
    """prefix is str for most subsystems, None for crosscutting."""
    from pmmcp.prompts.specialist import _SPECIALIST_KNOWLEDGE

    for subsystem, entry in _SPECIALIST_KNOWLEDGE.items():
        if subsystem == "crosscutting":
            assert entry["prefix"] is None, "crosscutting prefix must be None"
        else:
            assert isinstance(entry["prefix"], str), f"{subsystem} prefix must be str"
            assert len(entry["prefix"]) > 0, f"{subsystem} prefix must not be empty"


# ---------------------------------------------------------------------------
# T006: _specialist_investigate_impl — per-subsystem keywords
# ---------------------------------------------------------------------------


def test_specialist_impl_cpu_keywords():
    """CPU specialist content contains domain-specific keywords."""
    from pmmcp.prompts.specialist import _specialist_investigate_impl

    result = _specialist_investigate_impl("cpu")
    assert isinstance(result, list)
    assert len(result) >= 1
    assert result[0]["role"] == "user"
    text = result[0]["content"]
    for keyword in ("steal time", "runqueue"):
        assert keyword.lower() in text.lower(), f"CPU missing keyword: {keyword}"


def test_specialist_impl_memory_keywords():
    """Memory specialist content contains domain-specific keywords."""
    from pmmcp.prompts.specialist import _specialist_investigate_impl

    text = _specialist_investigate_impl("memory")[0]["content"]
    for keyword in ("swap", "OOM"):
        assert keyword.lower() in text.lower(), f"Memory missing keyword: {keyword}"


def test_specialist_impl_disk_keywords():
    """Disk specialist content contains domain-specific keywords."""
    from pmmcp.prompts.specialist import _specialist_investigate_impl

    text = _specialist_investigate_impl("disk")[0]["content"]
    for keyword in ("IOPS", "queue"):
        assert keyword.lower() in text.lower(), f"Disk missing keyword: {keyword}"


def test_specialist_impl_network_keywords():
    """Network specialist content contains domain-specific keywords."""
    from pmmcp.prompts.specialist import _specialist_investigate_impl

    text = _specialist_investigate_impl("network")[0]["content"]
    for keyword in ("dropped", "bandwidth"):
        assert keyword.lower() in text.lower(), f"Network missing keyword: {keyword}"


def test_specialist_impl_process_keywords():
    """Process specialist content contains domain-specific keywords."""
    from pmmcp.prompts.specialist import _specialist_investigate_impl

    text = _specialist_investigate_impl("process")[0]["content"]
    for keyword in ("zombie", "context switch"):
        assert keyword.lower() in text.lower(), f"Process missing keyword: {keyword}"


def test_specialist_impl_crosscutting_keywords():
    """Crosscutting specialist references pcp_quick_investigate."""
    from pmmcp.prompts.specialist import _specialist_investigate_impl

    text = _specialist_investigate_impl("crosscutting")[0]["content"]
    assert "pcp_quick_investigate" in text, "Crosscutting missing pcp_quick_investigate"


# ---------------------------------------------------------------------------
# T007: invalid subsystem error handling
# ---------------------------------------------------------------------------


def test_specialist_impl_invalid_subsystem_returns_error():
    """Invalid subsystem returns error message, not exception."""
    from pmmcp.prompts.specialist import _specialist_investigate_impl

    result = _specialist_investigate_impl("bogus")
    assert isinstance(result, list)
    assert len(result) >= 1
    text = result[0]["content"]
    assert "error" in text.lower() or "unknown" in text.lower() or "invalid" in text.lower()


# ---------------------------------------------------------------------------
# T008: specialist mandates pcp_discover_metrics
# ---------------------------------------------------------------------------


def test_specialist_impl_mandates_discover_metrics():
    """Subsystems with a prefix mandate pcp_discover_metrics(prefix=...)."""
    from pmmcp.prompts.specialist import _SPECIALIST_KNOWLEDGE, _specialist_investigate_impl

    for subsystem, entry in _SPECIALIST_KNOWLEDGE.items():
        if entry["prefix"] is not None:
            text = _specialist_investigate_impl(subsystem)[0]["content"]
            assert "pcp_discover_metrics" in text, f"{subsystem}: must mention pcp_discover_metrics"


# ---------------------------------------------------------------------------
# T009: optional parameter interpolation
# ---------------------------------------------------------------------------


def test_specialist_impl_interpolates_request():
    """request parameter appears in prompt content."""
    from pmmcp.prompts.specialist import _specialist_investigate_impl

    text = _specialist_investigate_impl("cpu", request="high latency")[0]["content"]
    assert "high latency" in text


def test_specialist_impl_interpolates_host():
    """host parameter appears in prompt content."""
    from pmmcp.prompts.specialist import _specialist_investigate_impl

    text = _specialist_investigate_impl("cpu", host="web01")[0]["content"]
    assert "web01" in text


def test_specialist_impl_interpolates_time_of_interest():
    """time_of_interest parameter appears in prompt content."""
    from pmmcp.prompts.specialist import _specialist_investigate_impl

    text = _specialist_investigate_impl("cpu", time_of_interest="2h ago")[0]["content"]
    assert "2h ago" in text


def test_specialist_impl_interpolates_lookback():
    """lookback parameter appears in prompt content."""
    from pmmcp.prompts.specialist import _specialist_investigate_impl

    text = _specialist_investigate_impl("cpu", lookback="4hours")[0]["content"]
    assert "4hours" in text
