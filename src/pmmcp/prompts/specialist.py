"""MCP Prompt: specialist_investigate — Deep domain expertise per subsystem.

Each subsystem gets a parameterized prompt encoding the reasoning of an
experienced performance engineer — not just namespace hints, but concrete
investigation heuristics, metric relationships, and interpretation guidance.
"""

from __future__ import annotations

from pmmcp.server import mcp

_SPECIALIST_KNOWLEDGE: dict[str, dict] = {
    "cpu": {
        "prefix": "kernel",
        "display_name": "CPU",
        "domain_knowledge": """\
1. Check `kernel.all.cpu.idle` first — if < 10%, the box is saturated. Decompose into user/sys/wait/steal.
2. High `kernel.all.cpu.sys` relative to user → excessive syscalls or lock contention (check context switches).
3. Non-zero steal time (`kernel.all.cpu.steal`) on VMs means the hypervisor is throttling — no amount of app tuning helps.
4. Compare `kernel.all.load` to `hinv.ncpu` — load > 2× ncpu is queueing, load > 4× is pathological.
5. Runqueue depth (`kernel.all.runnable`) sustained > ncpu signals CPU starvation; correlate with load average.
6. Per-CPU imbalance: if one CPU is pegged at 100% while others idle, suspect single-threaded bottleneck or IRQ affinity.
7. High iowait (`kernel.all.cpu.wait.total`) with low user/sys → the CPU is waiting on I/O, investigate disk/network.
8. Sudden CPU spike with no workload change → check for runaway process, cron job, or garbage collection storm.""",
        "report_guidance": """\
For each finding report: metric name, observed value (as %), baseline comparison, \
affected time window, and severity (critical/warning/info). Express CPU values as \
percentages normalised by hinv.ncpu.""",
    },
    "memory": {
        "prefix": "mem",
        "display_name": "Memory",
        "domain_knowledge": """\
1. Compare `mem.util.used` vs `mem.physmem` for utilisation — but `mem.util.available` is the real signal (includes reclaimable cache).
2. Any swap activity (`mem.vmstat.pswpin`, `mem.vmstat.pswpout` > 0) is a red flag — even small swap rates crush latency.
3. OOM killer events: check `mem.vmstat.oom_kill` — non-zero means the kernel killed processes to free memory.
4. Page fault rates (`mem.vmstat.pgfault`, `mem.vmstat.pgmajfault`) — major faults mean disk reads, not just TLB misses.
5. Slab growth (`mem.vmstat.nr_slab_reclaimable`, `nr_slab_unreclaimable`) — unreclaimable slab bloat is a kernel memory leak.
6. Huge page usage (`mem.util.hugepagesTotalBytes` vs `mem.util.hugepagesFreeBytes`) — misconfig wastes reserved memory.
7. Buffer/cache ratio: high `mem.util.bufmem` + `mem.util.cached` with low `mem.util.free` is normal — Linux aggressively caches.
8. Memory pressure trend: plot `mem.util.available` over time — a steady decline indicates a leak even if current usage looks OK.""",
        "report_guidance": """\
For each finding report: metric name, observed value in human units (MB/GB), \
percentage of total memory, trend direction (stable/rising/falling), and severity. \
Always distinguish between 'used' and 'available' — they tell different stories.""",
    },
    "disk": {
        "prefix": "disk",
        "display_name": "Disk I/O",
        "domain_knowledge": """\
1. Check `disk.dev.avactive` (ms per second busy) — > 700ms means the device is saturated.
2. IOPS: `rate(disk.dev.read)` + `rate(disk.dev.write)` — know your device limits (SSD: 10K-100K, HDD: 100-200).
3. Queue depth (`disk.dev.aveq`) sustained > 1 for HDD or > 32 for NVMe indicates saturation.
4. Throughput: `rate(disk.dev.read_bytes)` + `rate(disk.dev.write_bytes)` — compare to device spec (SATA SSD: ~500MB/s, NVMe: 3-7GB/s).
5. I/O latency = avactive / (reads + writes) — > 10ms for SSD or > 20ms for HDD is slow.
6. Read vs write ratio: heavy writes with journaling FS (ext4, xfs) amplify actual I/O — check for write-behind flush storms.
7. Correlate disk saturation with CPU iowait (`kernel.all.cpu.wait.total`) — if both high, disk is the bottleneck.
8. Per-device breakdown matters: one saturated device with others idle → workload imbalance or partition misplacement.""",
        "report_guidance": """\
For each finding report: device name, metric, observed value in human units \
(IOPS, MB/s, ms latency), device utilisation %, and severity. Always identify \
which specific device is affected.""",
    },
    "network": {
        "prefix": "network",
        "display_name": "Network",
        "domain_knowledge": """\
1. Bandwidth: `rate(network.interface.in.bytes)` + `rate(network.interface.out.bytes)` — compare to link speed.
2. Packet drops (`network.interface.in.drops`, `network.interface.out.drops`) — ANY non-zero sustained rate is a problem.
3. Error counters (`network.interface.in.errors`, `network.interface.out.errors`) — indicate hardware/driver issues or duplex mismatch.
4. TCP retransmits (`network.tcp.retranssegs`) — high retransmit rate kills throughput regardless of bandwidth.
5. Connection states: `network.tcp.currestab` for active connections — sudden spike may indicate connection storm or DDoS.
6. Per-interface breakdown: aggregate numbers hide problems — a saturated eth0 with idle eth1 suggests missing bonding or routing issues.
7. Dropped packets with no errors → buffer exhaustion (ring buffer too small) or CPU too slow to process incoming packets.
8. Compare inbound vs outbound — asymmetric traffic patterns help identify whether the host is a client, server, or relay.""",
        "report_guidance": """\
For each finding report: interface name, metric, observed rate in human units \
(KB/s, MB/s, packets/s), percentage of link capacity if known, and severity. \
Always identify which interface is affected.""",
    },
    "process": {
        "prefix": "proc",
        "display_name": "Process",
        "domain_knowledge": """\
1. Total process count (`proc.nprocs`) — sudden increase suggests fork bomb or runaway spawn loop.
2. Zombie processes (`proc.runq.defunct`) — non-zero means parent isn't reaping children; indicates buggy service.
3. Context switch rate (`kernel.all.pswitch`) — sustained high rate (>100K/s) with no throughput gain suggests lock contention.
4. Run queue depth (`proc.runq.runnable`) vs sleeping (`proc.runq.sleeping`) — runnable >> ncpu means CPU starvation.
5. Per-process CPU/memory via hotproc (if available) — identifies the specific process consuming resources.
6. Blocked processes (`proc.runq.blocked`) — processes stuck in uninterruptible sleep, usually waiting on I/O.
7. Thread count trends — growing thread count over time without corresponding workload increase suggests thread pool leak.
8. New process creation rate (`rate(proc.nprocs)`) — high churn (many short-lived processes) wastes fork/exec overhead.""",
        "report_guidance": """\
For each finding report: process metric, observed value, comparison to healthy \
baseline (e.g., normal process count), trend direction, and severity. Identify \
specific processes by name/PID when hotproc data is available.""",
    },
    "crosscutting": {
        "prefix": None,
        "display_name": "Cross-Cutting",
        "domain_knowledge": """\
1. Start with `pcp_quick_investigate` to get a ranked overview of anomalies across ALL subsystems.
2. Correlate CPU wait with disk I/O — high iowait + high disk avactive = disk bottleneck, not CPU issue.
3. Correlate memory pressure with swap activity and disk I/O — swap causes disk I/O which causes CPU iowait (cascade).
4. Network retransmits + high CPU sys → possible interrupt storm from NIC driver or small-packet flood.
5. Load average vs individual subsystems: high load with low CPU user% → the load is I/O-bound or memory-bound, not compute-bound.
6. Time correlation: find the exact moment things changed, then look at ALL subsystems at that timestamp.
7. Use `pcp_compare_windows` to quantify before/after — "it got 3× worse" is more useful than "it's bad."
8. Check derived metrics (derived.cpu.utilisation, derived.mem.utilisation, derived.disk.utilisation) for quick triage.""",
        "report_guidance": """\
For each finding report: the originating subsystem, metric, observed value, \
cross-subsystem correlation (e.g., "disk saturation causing CPU iowait"), \
timeline of events, and severity. Prioritise cascade effects — the upstream \
cause matters more than downstream symptoms.""",
    },
}

_VALID_SUBSYSTEMS = set(_SPECIALIST_KNOWLEDGE.keys())


def _specialist_investigate_impl(
    subsystem: str,
    request: str | None = None,
    host: str | None = None,
    time_of_interest: str | None = None,
    lookback: str | None = None,
) -> list[dict]:
    """Pure function returning the specialist_investigate prompt messages.

    Testable without MCP infrastructure.
    """
    if subsystem not in _VALID_SUBSYSTEMS:
        valid = ", ".join(sorted(_VALID_SUBSYSTEMS))
        return [
            {
                "role": "user",
                "content": (f"Error: unknown subsystem '{subsystem}'. Valid subsystems: {valid}"),
            }
        ]

    entry = _SPECIALIST_KNOWLEDGE[subsystem]
    display = entry["display_name"]
    prefix = entry["prefix"]

    # Build context clauses
    host_clause = f" on host **{host}**" if host else " across all monitored hosts"
    time_clause = f" centred on **{time_of_interest}**" if time_of_interest else ""
    lookback_clause = f" (lookback: **{lookback}**)" if lookback else ""
    request_clause = f"\n\n**Investigation request**: {request}" if request else ""

    # Discovery instruction — prefix-based for subsystems with a prefix
    if prefix:
        discovery = (
            f'Use `pcp_discover_metrics(prefix="{prefix}")` as your **primary discovery** '
            f"mechanism to enumerate all available {display} metrics. Do not rely solely on "
            f"`pcp_search` — it uses ranking that can miss metrics in less-populated namespaces."
        )
    else:
        discovery = (
            "This is a cross-cutting investigation — use `pcp_quick_investigate` to scan "
            "ALL namespaces for anomalies, then drill into the subsystems that surface problems."
        )

    content = f"""\
You are a **{display} specialist** conducting a focused performance investigation\
{host_clause}{time_clause}{lookback_clause}.{request_clause}

## Discovery

{discovery}

## Domain Knowledge — {display} Investigation

Apply these investigation heuristics systematically:

{entry["domain_knowledge"]}

## Reporting Structure

{entry["report_guidance"]}

## Workflow

1. **Discover** available metrics using the approach above.
2. **Fetch** key metrics with `pcp_fetch_timeseries` at an appropriate interval.
3. **Analyse** using the domain knowledge heuristics — check thresholds, correlations, trends.
4. **Report** each finding in the structured format described above.
5. **Recommend** next steps — immediate actions, further investigation, or escalation.

If you find no anomalies, say so explicitly — "no anomalies found in {display}" is a valid result.
"""

    return [{"role": "user", "content": content}]


@mcp.prompt()
def specialist_investigate(
    subsystem: str,
    request: str | None = None,
    host: str | None = None,
    time_of_interest: str | None = None,
    lookback: str | None = None,
) -> list[dict]:
    """Deep domain-expert investigation for a specific subsystem.

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
