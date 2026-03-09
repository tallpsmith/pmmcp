# Research: Specialist Agent Investigation Coordinator

## R1: Prompt vs Tool for Orchestration

**Decision**: Prompts, not tools. The coordinator and specialists are prompt-layer only.
**Rationale**: The spec explicitly states "no new tools needed." Prompts shape LLM behaviour — they instruct the calling LLM to use existing tools in a specific pattern. The orchestration happens in the LLM's reasoning, not in our server code.
**Alternatives**: A coordinator *tool* that programmatically dispatches sub-agents was considered but rejected — it would require MCP client capabilities we can't assume, and it couples the server to specific client architectures.

## R2: One Parameterized Prompt vs Six Separate Prompts

**Decision**: One `specialist_investigate` prompt with a `subsystem` parameter.
**Rationale**: Per spec clarification — keeps the MCP prompt registry clean. Domain knowledge is keyed internally via `_SPECIALIST_KNOWLEDGE` dict. If per-subsystem content grows unwieldy, can refactor to a data module later.
**Alternatives**: Six separate `specialist_cpu`, `specialist_memory`, etc. prompts — rejected as premature complexity.

## R3: Domain Knowledge Depth

**Decision**: Each subsystem block contains 5-8 concrete investigation heuristics (not just namespace hints).
**Rationale**: SC-002 requires "at least 5 domain-specific investigation steps or heuristics that go beyond namespace hints." The current `_SUBSYSTEM_HINTS` in `investigate.py` are 2-3 lines of namespace guidance. Specialists need the reasoning of an experienced performance engineer.
**Alternatives**: Referencing external knowledge bases or docs — rejected because prompts must be self-contained for offline/air-gapped use.

## R4: Primary Discovery Mechanism

**Decision**: Specialists mandate `pcp_discover_metrics(prefix=<namespace>)` as primary discovery, not `pcp_search`.
**Rationale**: Per spec FR-008. `pcp_search` uses RediSearch ranking which favours dominant namespaces. Prefix-based discovery walks the metric tree and guarantees coverage within the namespace. `pcp_search` remains useful for keyword exploration when the metric name pattern is unknown.
**Alternatives**: Relying solely on bumped `pcp_search(limit=50)` — rejected per spec clarification as insufficient (ranking bias persists at any limit).

## R5: Parallel vs Sequential Client Support

**Decision**: Coordinator prompt includes instructions for both modes — parallel when client supports sub-agents, sequential fallback otherwise.
**Rationale**: FR-005 requires capability awareness. Claude Code can dispatch sub-agents; Claude Desktop (as of 2026-03) cannot. The prompt must work in both environments without code changes.
**Alternatives**: Detecting client capabilities at the MCP protocol level — not feasible; the server doesn't know the client's dispatch capabilities.

## R6: Structured Report Format

**Decision**: Lightweight per-finding structure: metric, severity, direction, summary. Matches existing `pcp_quick_investigate` output shape.
**Rationale**: Per spec clarification. Consistent structure makes cross-referencing reliable in the synthesis phase. Not a rigid schema — the LLM fills it naturally.
**Alternatives**: JSON-structured output — rejected as overly rigid for prompt-directed LLM output.

## R7: Search Limit Bump Value

**Decision**: 20→50 (not 100 or higher).
**Rationale**: Per spec FR-007. 50 is the spec's explicit value. The existing `pcp_search` docstring already suggests "For exploration use 50." This is a secondary improvement — prefix-based discovery is the primary fix.
**Alternatives**: Higher values (100, 200) — rejected per spec. Users can still pass explicit `limit=` for larger searches.
