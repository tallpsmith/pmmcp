# Data Model: Specialist Historical Baselining

**Feature**: 011-specialist-baselining | **Date**: 2026-03-10

## Overview

This feature adds no new Pydantic models or database entities. All changes are to prompt text templates that guide LLM behaviour. The "data model" here describes the report structure fields added to prompt output guidance.

## Report Structure Fields (Prompt-Guided)

These fields are instructed in the specialist report guidance — the LLM produces them as structured text. They are NOT enforced by code; they are advisory prompt instructions.

### Finding Classification

| Field | Type (advisory) | Values | Description |
|-------|-----------------|--------|-------------|
| `classification` | enum string | ANOMALY, RECURRING, BASELINE | Whether the finding is new (anomaly), a known periodic pattern, or normal baseline behaviour |
| `baseline_context` | free text | — | Human-readable comparison to the 7-day baseline (e.g., "CPU idle has been below 15% for the past 7 days") |
| `severity_despite_baseline` | enum string | critical, warning, info, none | Threshold-based severity independent of classification. A BASELINE finding with severity=warning means "your normal is degraded" |

### Classification Decision Rules (LLM Heuristics)

| Classification | Condition |
|---------------|-----------|
| ANOMALY | `pcp_detect_anomalies` reports significant z-score AND pattern does not recur at consistent times in the 7-day timeseries |
| RECURRING | 7-day timeseries shows repeated spikes at consistent times of day (batch jobs, log rotation, backups, cron jobs) |
| BASELINE | Current values are within normal range based on 7-day history (low z-score or no anomaly detected) |

### Coordinator Ranking Order

| Priority | Classification | Severity Sort |
|----------|---------------|---------------|
| 1 (highest) | ANOMALY | critical → warning → info |
| 2 | RECURRING | critical → warning → info |
| 3 (lowest) | BASELINE | critical → warning → info |

## Existing Entities (Unchanged)

- `_SPECIALIST_KNOWLEDGE` dict in `specialist.py` — keys: `prefix`, `display_name`, `domain_knowledge`, `report_guidance`. Structure unchanged; content updated.
- `_specialist_investigate_impl()` signature — unchanged (subsystem, request, host, time_of_interest, lookback)
- `_coordinate_investigation_impl()` signature — unchanged (request, host, time_of_interest, lookback)
- `pcp_detect_anomalies` tool — unchanged (metrics, recent_start, recent_end, baseline_start, baseline_end, z_score_threshold, host, interval)
