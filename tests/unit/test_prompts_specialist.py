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


# ---------------------------------------------------------------------------
# T002: Baseline step presence in domain subsystems
# ---------------------------------------------------------------------------

_DOMAIN_SUBSYSTEMS = ("cpu", "memory", "disk", "network", "process")


def test_baseline_step_present_in_domain_subsystems():
    """T002: Domain specialists include a Baseline step referencing
    pcp_fetch_timeseries, pcp_detect_anomalies, and 7-day window."""
    from pmmcp.prompts.specialist import _specialist_investigate_impl

    for sub in _DOMAIN_SUBSYSTEMS:
        text = _specialist_investigate_impl(sub)[0]["content"]
        assert "baseline" in text.lower(), f"{sub}: missing Baseline step"
        assert "pcp_fetch_timeseries" in text, (
            f"{sub}: Baseline must reference pcp_fetch_timeseries"
        )
        assert "pcp_detect_anomalies" in text, (
            f"{sub}: Baseline must reference pcp_detect_anomalies"
        )
        assert "7-day" in text.lower() or "7 day" in text.lower(), (
            f"{sub}: Baseline must reference 7-day window"
        )


# ---------------------------------------------------------------------------
# T003: Cross-cutting does NOT include Baseline step
# ---------------------------------------------------------------------------


def test_baseline_step_absent_from_crosscutting():
    """T003: Cross-cutting specialist does NOT have a Baseline workflow step."""
    from pmmcp.prompts.specialist import _specialist_investigate_impl

    text = _specialist_investigate_impl("crosscutting")[0]["content"]
    # Cross-cutting should not have a numbered "Baseline" step in its workflow
    # (it may reference the word "baseline" in domain knowledge for classification,
    # but should NOT have a "## Baseline" or "**Baseline**" workflow step)
    workflow_section = text.split("## Workflow")[1] if "## Workflow" in text else ""
    assert "baseline" not in workflow_section.lower(), (
        "Cross-cutting must NOT have a Baseline workflow step"
    )


# ---------------------------------------------------------------------------
# T004: Classification fields in report structure
# ---------------------------------------------------------------------------


def test_classification_fields_in_domain_report_guidance():
    """T004: Domain specialist output includes classification, ANOMALY,
    RECURRING, BASELINE, baseline_context, severity_despite_baseline."""
    from pmmcp.prompts.specialist import _specialist_investigate_impl

    required_terms = [
        "classification",
        "ANOMALY",
        "RECURRING",
        "BASELINE",
        "baseline_context",
        "severity_despite_baseline",
    ]
    for sub in _DOMAIN_SUBSYSTEMS:
        text = _specialist_investigate_impl(sub)[0]["content"]
        for term in required_terms:
            assert term in text, f"{sub}: missing '{term}' in report guidance"


# ---------------------------------------------------------------------------
# T005: Narrative guidance for chronic problems
# ---------------------------------------------------------------------------


def test_chronic_problem_narrative_guidance():
    """T005: Domain specialists include narrative guidance for BASELINE-classified
    findings — explaining chronic problems in human terms."""
    from pmmcp.prompts.specialist import _specialist_investigate_impl

    for sub in _DOMAIN_SUBSYSTEMS:
        text = _specialist_investigate_impl(sub)[0]["content"].lower()
        has_chronic_language = any(
            phrase in text
            for phrase in (
                "not a new problem",
                "your normal",
                "chronic",
                "historically typical",
                "been this way",
            )
        )
        assert has_chronic_language, (
            f"{sub}: missing narrative guidance for chronic/baseline findings"
        )


# ---------------------------------------------------------------------------
# T010-T013: Baseline-aware heuristics in domain knowledge
# ---------------------------------------------------------------------------


def test_cpu_domain_knowledge_baseline_heuristic():
    """T010: CPU domain_knowledge includes guidance to check whether current
    CPU levels are typical for this time of day over the past week."""
    from pmmcp.prompts.specialist import _SPECIALIST_KNOWLEDGE

    dk = _SPECIALIST_KNOWLEDGE["cpu"]["domain_knowledge"].lower()
    assert "time of day" in dk or "past week" in dk or "7-day" in dk or "baseline" in dk, (
        "CPU domain_knowledge missing baseline-aware heuristic"
    )


def test_memory_domain_knowledge_baseline_heuristic():
    """T011: Memory domain_knowledge includes guidance to compare memory growth
    against the 7-day baseline to distinguish leaks from normal working-set growth."""
    from pmmcp.prompts.specialist import _SPECIALIST_KNOWLEDGE

    dk = _SPECIALIST_KNOWLEDGE["memory"]["domain_knowledge"].lower()
    has_baseline = any(
        phrase in dk
        for phrase in ("7-day", "baseline", "working-set growth", "normal growth", "past week")
    )
    assert has_baseline, "Memory domain_knowledge missing baseline-aware leak heuristic"


def test_disk_domain_knowledge_baseline_heuristic():
    """T012: Disk domain_knowledge includes guidance to check whether I/O spikes
    recur at the same time daily (scheduled jobs)."""
    from pmmcp.prompts.specialist import _SPECIALIST_KNOWLEDGE

    dk = _SPECIALIST_KNOWLEDGE["disk"]["domain_knowledge"].lower()
    has_schedule = any(
        phrase in dk
        for phrase in ("same time daily", "scheduled job", "recur", "backup", "log rotation")
    )
    assert has_schedule, "Disk domain_knowledge missing baseline-aware scheduled job heuristic"


def test_network_domain_knowledge_baseline_heuristic():
    """T013a: Network domain_knowledge contains at least one baseline-aware heuristic."""
    from pmmcp.prompts.specialist import _SPECIALIST_KNOWLEDGE

    dk = _SPECIALIST_KNOWLEDGE["network"]["domain_knowledge"].lower()
    has_baseline = any(
        phrase in dk for phrase in ("baseline", "7-day", "past week", "normal variance")
    )
    assert has_baseline, "Network domain_knowledge missing baseline-aware heuristic"


def test_process_domain_knowledge_baseline_heuristic():
    """T013b: Process domain_knowledge contains at least one baseline-aware heuristic."""
    from pmmcp.prompts.specialist import _SPECIALIST_KNOWLEDGE

    dk = _SPECIALIST_KNOWLEDGE["process"]["domain_knowledge"].lower()
    has_baseline = any(
        phrase in dk for phrase in ("baseline", "7-day", "past week", "7-day pattern")
    )
    assert has_baseline, "Process domain_knowledge missing baseline-aware heuristic"


# ---------------------------------------------------------------------------
# T020-T021: Graceful degradation when baseline data is insufficient
# ---------------------------------------------------------------------------


def test_graceful_degradation_fallback_instruction():
    """T020: Domain specialists include instructions to fall back to
    threshold-only analysis if pcp_detect_anomalies returns insufficient data."""
    from pmmcp.prompts.specialist import _specialist_investigate_impl

    for sub in _DOMAIN_SUBSYSTEMS:
        text = _specialist_investigate_impl(sub)[0]["content"].lower()
        assert "threshold-only" in text or "threshold only" in text, (
            f"{sub}: missing threshold-only fallback instruction"
        )
        assert "insufficient" in text or "fall back" in text or "fallback" in text, (
            f"{sub}: missing fallback trigger language"
        )


def test_graceful_degradation_report_limitation():
    """T021: Domain specialists include instructions to note 'insufficient baseline'
    or similar limitation wording in the report when degraded."""
    from pmmcp.prompts.specialist import _specialist_investigate_impl

    for sub in _DOMAIN_SUBSYSTEMS:
        text = _specialist_investigate_impl(sub)[0]["content"].lower()
        assert "insufficient baseline" in text, (
            f"{sub}: missing 'insufficient baseline' limitation note"
        )
