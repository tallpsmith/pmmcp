"""Shared statistical utilities for tool modules."""

from __future__ import annotations

import math


def _compute_stats(values: list[float]) -> dict:
    """Compute summary statistics for a list of numeric values.

    Returns mean, min, max, p95, stddev, and sample_count.
    """
    n = len(values)
    if n == 0:
        return {"mean": 0.0, "min": 0.0, "max": 0.0, "p95": 0.0, "stddev": 0.0, "sample_count": 0}

    mean = sum(values) / n
    minimum = min(values)
    maximum = max(values)

    sorted_vals = sorted(values)
    p95_idx = max(0, int(math.ceil(0.95 * n)) - 1)
    p95 = sorted_vals[p95_idx]

    variance = sum((v - mean) ** 2 for v in values) / n
    stddev = math.sqrt(variance)

    return {
        "mean": mean,
        "min": minimum,
        "max": maximum,
        "p95": p95,
        "stddev": stddev,
        "sample_count": n,
    }


def pearson_correlation(xs: list[float], ys: list[float]) -> float:
    """Compute the Pearson correlation coefficient between two equal-length sequences.

    Returns a value in [-1, 1].  Returns 0.0 if either sequence has zero variance
    or if the sequences are empty / have fewer than 2 elements.
    """
    n = len(xs)
    if n != len(ys) or n < 2:
        return 0.0

    mean_x = sum(xs) / n
    mean_y = sum(ys) / n

    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)

    denom = math.sqrt(var_x * var_y)
    if denom == 0.0:
        return 0.0

    return cov / denom


def _compute_rates(samples: list[dict]) -> list[float]:
    """Convert timestamped counter samples to per-second rate-of-change values.

    Each sample is ``{"timestamp": float, "value": float}``.  For consecutive
    pairs the rate is ``max(0, delta_v / delta_t)`` — clamped to zero on counter
    wraps.  Pairs with zero ``delta_t`` are silently skipped (avoids div-by-zero).
    """
    rates: list[float] = []
    for i in range(1, len(samples)):
        dt = samples[i]["timestamp"] - samples[i - 1]["timestamp"]
        if dt == 0.0:
            continue
        dv = samples[i]["value"] - samples[i - 1]["value"]
        rates.append(max(0.0, dv / dt))
    return rates


def outlier_flag(values: list[float], threshold: float = 2.0) -> list[bool]:
    """Flag values that deviate more than *threshold* standard deviations from the mean.

    Returns a list of booleans parallel to *values*.  All values are flagged False
    when the list is empty or has fewer than 2 elements, or when stddev is zero.
    """
    n = len(values)
    if n < 2:
        return [False] * n

    mean = sum(values) / n
    variance = sum((v - mean) ** 2 for v in values) / n
    stddev = math.sqrt(variance)

    if stddev == 0.0:
        return [False] * n

    return [abs(v - mean) > threshold * stddev for v in values]
