# Data Model: Specialist Agent Investigation Coordinator

## Entities

### 1. Specialist Knowledge Entry

Internal data structure (Python dict, not persisted). Keyed by subsystem name in `_SPECIALIST_KNOWLEDGE`.

| Field | Type | Description |
|-------|------|-------------|
| prefix | `str \| None` | PCP metric namespace prefix for `pcp_discover_metrics`. `None` for cross-cutting. |
| display_name | `str` | Human-readable subsystem name (e.g., "CPU", "Memory") |
| domain_knowledge | `str` | Multi-line markdown: investigation steps, heuristics, metric relationships |
| report_guidance | `str` | Per-finding structure guidance: metric, severity, direction, summary |

**Valid subsystem keys**: `cpu`, `memory`, `disk`, `network`, `process`, `crosscutting`

### 2. Prompt Arguments

#### `specialist_investigate`

| Argument | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| subsystem | `str` | Yes | — | One of: cpu, memory, disk, network, process, crosscutting |
| request | `str \| None` | No | `None` | What to investigate (e.g., "high latency") |
| host | `str \| None` | No | `None` | Target host (all hosts if omitted) |
| time_of_interest | `str \| None` | No | `"now"` | Center of investigation window |
| lookback | `str \| None` | No | `"2hours"` | Window size around time_of_interest |

#### `coordinate_investigation`

| Argument | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| request | `str` | Yes | — | What to investigate (e.g., "app is slow") |
| host | `str \| None` | No | `None` | Target host (all hosts if omitted) |
| time_of_interest | `str \| None` | No | `"now"` | Center of investigation window |
| lookback | `str \| None` | No | `"2hours"` | Window size around time_of_interest |

### 3. Prompt Output

Both prompts return `list[dict]` — a single-element list:

```python
[{"role": "user", "content": "<markdown investigation instructions>"}]
```

No new Pydantic models needed. No persistence. No API contracts beyond the MCP prompt protocol (already handled by FastMCP).

## Relationships

```
coordinate_investigation
    ├── dispatches → specialist_investigate(subsystem="cpu")
    ├── dispatches → specialist_investigate(subsystem="memory")
    ├── dispatches → specialist_investigate(subsystem="disk")
    ├── dispatches → specialist_investigate(subsystem="network")
    ├── dispatches → specialist_investigate(subsystem="process")
    └── dispatches → specialist_investigate(subsystem="crosscutting")

session_init
    └── references → coordinate_investigation (entry point guidance)
```

## State Transitions

N/A — prompts are stateless text generators. No lifecycle management needed.
