# Investigation Flow Architecture

pmmcp's investigation system uses a coordinator-specialist pattern: a single
coordinator prompt dispatches 6 domain-specialist sub-agents in parallel, each
carrying deep performance-engineering heuristics, then synthesises their findings
into a unified root-cause narrative.

## Entry Points

Five prompt templates serve as entry points. For a general "something is wrong"
investigation, `coordinate_investigation` (via `session_init`) is the recommended
default. The others target specific scenarios where you already know what you're
looking at.

```mermaid
flowchart TD
    U["🔍 User / LLM Agent"] --> SI["session_init\n<i>Register derived metrics,\nthen hand off to coordinator</i>"]
    U --> CI["coordinate_investigation\n<i>Broad multi-subsystem sweep</i>"]
    U --> IS["investigate_subsystem\n<i>Deep-dive into one subsystem</i>"]
    U --> IT["incident_triage\n<i>Symptom → root cause mapping</i>"]
    U --> CP["compare_periods\n<i>Before/after statistical comparison</i>"]
    U --> FH["fleet_health_check\n<i>All hosts × all subsystems</i>"]

    SI -->|"recommended\ndefault path"| CI

    style SI fill:#2d6a4f,color:#fff
    style CI fill:#2d6a4f,color:#fff
    style IS fill:#40916c,color:#fff
    style IT fill:#40916c,color:#fff
    style CP fill:#40916c,color:#fff
    style FH fill:#40916c,color:#fff
```

| Prompt | When to use |
|--------|------------|
| **`session_init`** | Start of any investigation session — registers derived metrics, then points to `coordinate_investigation` |
| **`coordinate_investigation`** | "Something is wrong and I don't know where" — the broad sweep |
| **`investigate_subsystem`** | You already know the subsystem (e.g., "disk is slow") |
| **`incident_triage`** | You have a symptom ("app is slow") and need to map it to subsystems |
| **`compare_periods`** | You have two time windows and want to quantify what changed |
| **`fleet_health_check`** | Routine health check across all hosts |

## Coordinator Dispatch

`coordinate_investigation` is the orchestration hub. It dispatches all 6
specialist sub-agents — preferring parallel execution — then synthesises their
reports into a single root-cause narrative with cross-subsystem correlation.

```mermaid
flowchart TD
    CI["coordinate_investigation"] --> D{"Dispatch Mode"}

    D -->|"parallel\n(preferred)"| PAR["All 6 specialists\nconcurrently"]
    D -->|"sequential\n(fallback)"| SEQ["CPU → Memory → Disk\n→ Network → Process\n→ Cross-cutting"]

    PAR --> CPU["specialist_investigate\n<b>CPU</b>\n<i>kernel.*</i>"]
    PAR --> MEM["specialist_investigate\n<b>Memory</b>\n<i>mem.*</i>"]
    PAR --> DISK["specialist_investigate\n<b>Disk I/O</b>\n<i>disk.*</i>"]
    PAR --> NET["specialist_investigate\n<b>Network</b>\n<i>network.*</i>"]
    PAR --> PROC["specialist_investigate\n<b>Process</b>\n<i>proc.*</i>"]
    PAR --> CROSS["specialist_investigate\n<b>Cross-Cutting</b>\n<i>all namespaces</i>"]

    CPU --> SYN["Phase 2: Synthesis"]
    MEM --> SYN
    DISK --> SYN
    NET --> SYN
    PROC --> SYN
    CROSS --> SYN

    SYN --> OUT["Unified Report\n• Root cause narrative\n• Timeline correlation\n• Findings ranked by severity\n• Concrete recommendations"]

    style CI fill:#2d6a4f,color:#fff
    style SYN fill:#d4a373,color:#000
    style OUT fill:#264653,color:#fff
```

### The 6 Specialist Domains

Each specialist carries domain-specific heuristics — concrete thresholds, metric
relationships, and interpretation rules from experienced performance engineers.

| Specialist | Metric prefix | Focus |
|-----------|--------------|-------|
| **CPU** | `kernel.*` | Idle/user/sys/wait/steal decomposition, load vs ncpu, runqueue depth, per-CPU imbalance |
| **Memory** | `mem.*` | Available vs used, swap activity, OOM kills, page faults, slab growth, leak detection |
| **Disk I/O** | `disk.*` | Device saturation, IOPS vs device limits, queue depth, latency, read/write ratio |
| **Network** | `network.*` | Bandwidth vs link speed, drops/errors, TCP retransmits, connection states, per-interface |
| **Process** | `proc.*` | Process count, zombies, context switches, runqueue, blocked processes, thread leaks |
| **Cross-Cutting** | _(all)_ | Uses `pcp_quick_investigate` for anomaly scan, then correlates across subsystems |

## Specialist Workflow

Every specialist follows the same 4-step discipline: discover what metrics exist,
fetch the data, analyse against domain heuristics, then report structured findings.
This prevents the common failure mode of querying metrics that don't exist on the
target host.

```mermaid
sequenceDiagram
    participant C as Coordinator
    participant S as Specialist
    participant T as pmmcp Tools

    C->>S: specialist_investigate(subsystem, host, ...)

    rect rgb(230, 240, 230)
        Note over S,T: 1. Discover
        S->>T: pcp_discover_metrics(prefix="kernel")
        T-->>S: Available metric names
    end

    rect rgb(230, 235, 245)
        Note over S,T: 2. Fetch
        S->>T: pcp_fetch_timeseries(names=[...])
        T-->>S: Time-series data
        S->>T: pcp_compare_windows(...) [optional]
        T-->>S: Statistical comparison
    end

    rect rgb(245, 235, 225)
        Note over S,T: 3. Analyse
        Note over S: Apply domain heuristics<br/>Check thresholds & correlations<br/>Identify anomalies
    end

    rect rgb(240, 230, 230)
        Note over S,T: 4. Report
        S-->>C: Structured findings<br/>(metric, value, severity,<br/>affected window, recommendation)
    end
```

## Synthesis Phase

After all specialists report (or fail — partial results are expected), the
coordinator synthesises findings:

1. **Cross-reference** — correlate findings across subsystems (e.g., CPU iowait +
   disk saturation → disk is the root cause)
2. **Timeline correlation** — the subsystem that changed first is the likely root
   cause
3. **Unified narrative** — tell the story of what happened, not just list findings
4. **Rank by impact** — order by severity and blast radius
5. **Recommend actions** — concrete next steps, not "investigate further"

The output follows a structured format: executive summary → root cause analysis →
findings by severity → recommendations → specialist status.
