# Investigation Hierarchy Guardrails — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Guide Claude toward the coordinator prompt instead of bypassing the investigation hierarchy, and add Grafana visualisation as Phase 3 of the coordinator workflow.

**Architecture:** Docstring additions to 4 tool functions, prompt content changes to 3 prompt modules, and 2 new config fields. No new tools, no new files beyond tests. All changes are text/config — no behavioural changes to existing tool logic.

**Tech Stack:** Python 3.11+, pydantic-settings, pytest

---

## Chunk 1: Config & Tool Docstrings

### Task 1: Add `grafana_folder` and `report_dir` config fields

**Note:** The design spec says `PmproxyConfig` but these are server-level settings (Grafana
folder, report output dir), not pmproxy connection settings. `ServerConfig` (env prefix
`PMMCP_`) is the correct home — `PmproxyConfig` (env prefix `PMPROXY_`) is for pmproxy
connection parameters only.

**Files:**
- Modify: `src/pmmcp/config.py`
- Create: `tests/unit/test_config.py`

- [ ] **Step 1: Write failing tests for new config fields**

```python
# tests/unit/test_config.py — create this file

def test_server_config_grafana_folder_default():
    """PMMCP_GRAFANA_FOLDER defaults to 'pmmcp-triage'."""
    from pmmcp.config import ServerConfig
    cfg = ServerConfig()
    assert cfg.grafana_folder == "pmmcp-triage"


def test_server_config_grafana_folder_env_override(monkeypatch):
    """PMMCP_GRAFANA_FOLDER can be overridden via env var."""
    from pmmcp.config import ServerConfig
    monkeypatch.setenv("PMMCP_GRAFANA_FOLDER", "my-triage")
    cfg = ServerConfig()
    assert cfg.grafana_folder == "my-triage"


def test_server_config_report_dir_default():
    """PMMCP_REPORT_DIR defaults to ~/.pmmcp/reports/."""
    from pmmcp.config import ServerConfig
    from pathlib import Path
    cfg = ServerConfig()
    assert cfg.report_dir == Path("~/.pmmcp/reports")


def test_server_config_report_dir_env_override(monkeypatch):
    """PMMCP_REPORT_DIR can be overridden via env var."""
    from pmmcp.config import ServerConfig
    from pathlib import Path
    monkeypatch.setenv("PMMCP_REPORT_DIR", "/tmp/reports")
    cfg = ServerConfig()
    assert cfg.report_dir == Path("/tmp/reports")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_config.py -v -k "grafana_folder or report_dir"`
Expected: FAIL — `ServerConfig` has no `grafana_folder` or `report_dir` attributes

- [ ] **Step 3: Add fields to ServerConfig**

In `src/pmmcp/config.py`, add two fields to `ServerConfig`:

```python
class ServerConfig(BaseSettings):
    transport: Literal["stdio", "streamable-http"] = "stdio"
    host: str = "127.0.0.1"
    port: int = 8080
    grafana_folder: str = "pmmcp-triage"
    report_dir: Path = Path("~/.pmmcp/reports")

    model_config = {"env_prefix": "PMMCP_"}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_config.py -v -k "grafana_folder or report_dir"`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/pmmcp/config.py tests/unit/test_config.py
git commit -m "feat: add grafana_folder and report_dir config fields

Per issue #10 — configurable Grafana folder (default pmmcp-triage)
and HTML fallback report directory (default ~/.pmmcp/reports)."
```

---

### Task 2: Add coordinator breadcrumbs to tool docstrings

**Files:**
- Modify: `src/pmmcp/tools/investigate.py:190-207` (pcp_quick_investigate docstring)
- Modify: `src/pmmcp/tools/timeseries.py:133-155` (pcp_fetch_timeseries docstring)
- Modify: `src/pmmcp/tools/anomaly.py:127-142` (pcp_detect_anomalies docstring)
- Modify: `src/pmmcp/tools/scanning.py:130-147` (pcp_scan_changes docstring)

No test file — docstring changes are not testable via unit tests (the MCP tool description is extracted from the docstring at registration time; testing it would require spinning up the full MCP server). The existing contract tests in `tests/contract/test_prompts.py` cover prompt registration; tool docstrings are verified by manual inspection.

- [ ] **Step 1: Add breadcrumb to `pcp_quick_investigate` docstring**

In `src/pmmcp/tools/investigate.py`, append after the `host` arg line (before the closing `"""`):

```python
    """Start here for open-ended investigation. Only requires a time of interest.

    ...existing docstring...

    Note: For broad 'something is wrong' investigations spanning multiple subsystems,
    prefer the ``coordinate_investigation`` prompt — it dispatches 6 specialist
    sub-agents in parallel for comprehensive coverage.
    """
```

- [ ] **Step 2: Add breadcrumb to `pcp_fetch_timeseries` docstring**

In `src/pmmcp/tools/timeseries.py`, append before the closing `"""`:

```python
    Note: For broad investigations, start with the ``coordinate_investigation`` prompt
    rather than fetching metrics directly — it orchestrates a full multi-subsystem sweep.
```

- [ ] **Step 3: Add breadcrumb to `pcp_detect_anomalies` docstring**

In `src/pmmcp/tools/anomaly.py`, append before the closing `"""`:

```python
    Note: For broad investigations, start with the ``coordinate_investigation`` prompt
    rather than running anomaly detection directly — it orchestrates a full multi-subsystem sweep.
```

- [ ] **Step 4: Add breadcrumb to `pcp_scan_changes` docstring**

In `src/pmmcp/tools/scanning.py`, append before the closing `"""`:

```python
    Note: For broad investigations, start with the ``coordinate_investigation`` prompt
    rather than scanning changes directly — it orchestrates a full multi-subsystem sweep.
```

- [ ] **Step 5: Run lint to verify no formatting issues**

Run: `uv run ruff check src/pmmcp/tools/investigate.py src/pmmcp/tools/timeseries.py src/pmmcp/tools/anomaly.py src/pmmcp/tools/scanning.py`
Expected: No errors

- [ ] **Step 6: Commit**

```bash
git add src/pmmcp/tools/investigate.py src/pmmcp/tools/timeseries.py src/pmmcp/tools/anomaly.py src/pmmcp/tools/scanning.py
git commit -m "feat: add coordinator breadcrumbs to tool docstrings

Tool descriptions are the last thing Claude reads before deciding what
to call. These one-liners nudge toward coordinate_investigation for
broad investigations instead of bypassing the prompt hierarchy."
```

---

## Chunk 2: Prompt Changes

### Task 3: Make `session_init` assertive about coordinator + add Grafana preflight

**Files:**
- Modify: `src/pmmcp/prompts/session_init.py`
- Modify: `tests/unit/test_prompts_session_init.py`

- [ ] **Step 1: Write failing tests for assertive language and Grafana preflight**

Append to `tests/unit/test_prompts_session_init.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_prompts_session_init.py -v -k "assertive or before_derived or preflight or fallback_cascade"`
Expected: FAIL — current session_init lacks assertive language, preflight, and fallback

- [ ] **Step 3: Rewrite `_session_init_impl` content**

In `src/pmmcp/prompts/session_init.py`, restructure the `content` f-string in `_session_init_impl`. The new structure is:

1. **IMPORTANT block** (top) — assertive coordinator guidance
2. **Grafana Preflight** — datasource discovery + validation workflow
3. **Step 1** — Register Derived Metrics (existing, unchanged)
4. **Step 2** — Verify Availability (existing, unchanged)
5. **Step 3** — Report Results (existing, unchanged)

Replace the `content = f"""..."""` block with:

```python
    content = f"""\
You are initialising a PCP monitoring session{host_clause}{timerange_clause}.

## IMPORTANT — Investigation Entry Point

**ALWAYS** use the `coordinate_investigation` prompt for broad performance investigations. \
It dispatches 6 specialist sub-agents (cpu, memory, disk, network, process, crosscutting) \
in parallel, then synthesises findings into a unified root-cause narrative with \
cross-subsystem correlation. **Do NOT** call individual tools (`pcp_fetch_timeseries`, \
`pcp_detect_anomalies`, etc.) or specialist prompts directly unless you have a specific, \
targeted question about a single known metric.

## Grafana Preflight — Datasource Discovery

Before any investigation, check whether Grafana visualisation is available:

1. Call `mcp-grafana.list_datasources` to enumerate configured datasources.
2. Look for a datasource of type `performancecopilot-valkey-datasource` or \
`performancecopilot-vector-datasource`.
3. If found, note its **UID** and **URL** for later dashboard creation.
4. **Match**: Grafana features enabled — investigation prompts will create dashboards \
in the `pmmcp-triage` folder, named `YYYY-MM-DD <summary>`, tagged `pmmcp-generated`.
5. **No match / no mcp-grafana**: Grafana unavailable — fall back to text output or \
offer an HTML report. This is not an error; pmmcp works fully standalone.

## Step 1 — Register Derived Metrics

Call `pcp_derive_metric` for each metric below:

{metric_lines}

Example call for the first metric:
```
pcp_derive_metric(
    name="derived.cpu.utilisation",
    expr="100 - rate(kernel.all.cpu.idle) / hinv.ncpu / 10"
)
```

Registration is idempotent — re-registering an existing name overwrites silently.

## Step 2 — Verify Availability

After registering, verify each derived metric is resolvable by calling `pcp_fetch_live`:

{verify_lines}

## Step 3 — Report Results

For each metric, report whether registration and verification succeeded or failed:

- **Success**: `derived.cpu.utilisation` registered and verified ✓
- **Failure**: `derived.disk.utilisation` failed verification — \
`disk.all.avactive` may not be available on this host. Note and continue.

**Do not abort if one or more verifications fail.** Report which metrics are available \
and which are not, so downstream investigations know which derived metrics can be used.
"""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_prompts_session_init.py -v`
Expected: ALL PASS (existing + new tests)

- [ ] **Step 5: Commit**

```bash
git add src/pmmcp/prompts/session_init.py tests/unit/test_prompts_session_init.py
git commit -m "feat: assertive coordinator guidance + Grafana preflight in session_init

Moves coordinator reference from afterthought to IMPORTANT block at top.
Adds Grafana datasource discovery workflow with fallback cascade.
Per issue #10."
```

---

### Task 4: Add hierarchy context to specialist prompt docstring

**Files:**
- Modify: `src/pmmcp/prompts/specialist.py:260-281` (docstring of `specialist_investigate`)
- Test: `tests/unit/test_prompts_specialist.py`

- [ ] **Step 1: Write failing test for hierarchy context**

Append to `tests/unit/test_prompts_specialist.py`:

```python
def test_specialist_docstring_references_coordinator():
    """specialist_investigate docstring references coordinate_investigation as parent."""
    from pmmcp.prompts.specialist import specialist_investigate

    docstring = specialist_investigate.__doc__
    assert "coordinate_investigation" in docstring, (
        "specialist_investigate docstring must reference coordinate_investigation"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_prompts_specialist.py::test_specialist_docstring_references_coordinator -v`
Expected: FAIL — current docstring doesn't mention coordinate_investigation

- [ ] **Step 3: Update specialist_investigate docstring**

In `src/pmmcp/prompts/specialist.py`, update the `specialist_investigate` docstring:

```python
@mcp.prompt()
def specialist_investigate(
    subsystem: str,
    request: str | None = None,
    host: str | None = None,
    time_of_interest: str | None = None,
    lookback: str | None = None,
) -> list[dict]:
    """Deep domain-expert investigation for a specific subsystem.

    Typically dispatched by ``coordinate_investigation`` as part of a parallel
    6-specialist sweep. For broad 'something is wrong' investigations, start
    with the coordinator prompt instead of calling this directly.

    Each subsystem (cpu, memory, disk, network, process, crosscutting)
    carries concrete investigation heuristics, metric relationships, and
    interpretation guidance from an experienced performance engineer.

    Args:
        subsystem: One of: cpu, memory, disk, network, process, crosscutting
        request: What to investigate (e.g., "high latency") — optional
        host: Target host (all hosts if omitted) — optional
        time_of_interest: Centre of investigation window (default: now) — optional
        lookback: Window size around time_of_interest (default: 2hours) — optional
    """
    return _specialist_investigate_impl(subsystem, request, host, time_of_interest, lookback)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_prompts_specialist.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/pmmcp/prompts/specialist.py tests/unit/test_prompts_specialist.py
git commit -m "feat: add hierarchy context to specialist_investigate docstring

Tells Claude this prompt is typically dispatched by the coordinator,
nudging toward coordinate_investigation for broad investigations."
```

---

### Task 5: Add Phase 3 visualisation to coordinator prompt

**Files:**
- Modify: `src/pmmcp/prompts/coordinator.py`
- Modify: `tests/unit/test_prompts_coordinator.py`

- [ ] **Step 1: Write failing tests for Phase 3 visualisation**

Append to `tests/unit/test_prompts_coordinator.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_prompts_coordinator.py -v -k "phase3 or grafana_conventions or fallback_cascade or deeplink"`
Expected: FAIL — current coordinator has no Phase 3

- [ ] **Step 3: Add Phase 3 to coordinator prompt content**

In `src/pmmcp/prompts/coordinator.py`, append Phase 3 after the `## Output Structure` section in the `content` f-string (before the closing `"""`):

```python
## Phase 3 — Visualisation

After synthesis, create a visual record of the investigation:

### Grafana Dashboard (preferred)

If `mcp-grafana` tools are available in this session:

1. Create (or find) a folder named **`pmmcp-triage`** using `mcp-grafana.search_folders` / \
`mcp-grafana.create_folder`.
2. Create a dashboard using `mcp-grafana.update_dashboard`:
   - **Title**: `YYYY-MM-DD <short summary>` (e.g., `2026-03-10 memory cascade saas-prod-01`)
   - **Tags**: always include `pmmcp-generated`
   - **Folder**: `pmmcp-triage`
   - **Panels**: one panel per key finding — memory, swap, CPU, disk, network as relevant. \
Use the PCP datasource UID discovered during session preflight.
3. Call `mcp-grafana.generate_deeplink` and return the dashboard URL to the user.

### HTML Fallback

If mcp-grafana is unavailable, offer to generate a self-contained HTML report:
- Save to the configured report directory (default `~/.pmmcp/reports/`)
- Name: `YYYY-MM-DD-<short-summary>.html`
- Include investigation summary, data tables, and narrative

### Text Fallback

If the user declines both, the synthesised text output from Phase 2 stands on its own.

### Auto-Trigger Heuristic

If your investigation has surfaced findings across 3+ metrics or 2+ subsystems, and you \
have not already created a visualisation, proactively offer to create a dashboard — don't \
wait to be asked.
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_prompts_coordinator.py -v`
Expected: ALL PASS (existing + new tests)

- [ ] **Step 5: Commit**

```bash
git add src/pmmcp/prompts/coordinator.py tests/unit/test_prompts_coordinator.py
git commit -m "feat: add Phase 3 visualisation to coordinator prompt

After synthesis, coordinator now instructs Claude to create a Grafana
dashboard (pmmcp-triage folder, YYYY-MM-DD naming, pmmcp-generated tag)
with fallback cascade to HTML or text. Per issue #10."
```

---

### Task 6: Update CLAUDE.md and README.md with new conventions

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md` (new env vars: `PMMCP_GRAFANA_FOLDER`, `PMMCP_REPORT_DIR`)

- [ ] **Step 1: Add Grafana dashboard conventions section**

In `CLAUDE.md`, add after the "Grafana Compose Gotchas" section:

```markdown
## Grafana Dashboard Conventions (Investigation Output)

When creating dashboards as part of an investigation:

| Convention | Value |
|-----------|-------|
| Folder | `pmmcp-triage` (configurable via `PMMCP_GRAFANA_FOLDER`) |
| Naming | `YYYY-MM-DD <short summary>` (e.g., `2026-03-10 memory cascade saas-prod-01`) |
| Tagging | Always include `pmmcp-generated` |
| Deeplink | After creation, call `generate_deeplink` and return URL to user |
| Auto-trigger | Offer visualisation when findings span 3+ metrics or 2+ subsystems |

## Investigation Prompt Hierarchy

The investigation prompt hierarchy is:

```
session_init → coordinate_investigation → specialist_investigate (×6)
```

- **ALWAYS** start broad investigations with `coordinate_investigation`
- **DO NOT** call raw tools (`pcp_fetch_timeseries`, `pcp_detect_anomalies`) directly for open-ended investigations
- Specialist prompts are dispatched by the coordinator — don't call them directly unless targeting a specific subsystem
```

- [ ] **Step 2: Add new env vars to README.md configuration table**

In `README.md`, find the configuration/environment variables section and add:

| Variable | Default | Description |
|----------|---------|-------------|
| `PMMCP_GRAFANA_FOLDER` | `pmmcp-triage` | Grafana folder for investigation dashboards |
| `PMMCP_REPORT_DIR` | `~/.pmmcp/reports` | Output directory for HTML fallback reports |

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md README.md
git commit -m "docs: add investigation hierarchy, Grafana conventions, and new env vars"
```

---

### Task 7: Pre-push sanity check

- [ ] **Step 1: Sync dev environment**

Run: `uv sync --extra dev`

- [ ] **Step 2: Run full test suite with coverage**

Run: `uv run pytest --cov=pmmcp --cov-report=term-missing`
Expected: ALL PASS, coverage ≥80%

- [ ] **Step 3: Run lint and format**

Run: `uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/`
Expected: No errors

- [ ] **Step 4: Run pre-push sanity (or `just ci` in VM)**

Run: `just ci` (VM) or `./pre-commit.sh` (host with podman)
Expected: All green

- [ ] **Step 5: Push**

Run: `git push`
