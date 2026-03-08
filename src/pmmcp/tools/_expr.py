"""Shared series expression builder with escaping and chunking.

pmproxy has a ~8KB URL parameter limit (MAX_PARAMS_SIZE). Each metric name
averages ~55 chars in an expression. 120 × 55 ≈ 6600 bytes — safely under
the limit with room for host qualifiers and other params.
"""

from __future__ import annotations

MAX_EXPR_METRICS = 120


def _escape_host(host: str) -> str:
    """Escape chars that break pmproxy series expression parsing."""
    return host.replace("\\", "\\\\").replace('"', '\\"')


def build_series_expr(names: list[str], host: str = "") -> str:
    """Build a single pmproxy series query expression.

    Raises ValueError if names exceeds MAX_EXPR_METRICS.
    """
    if len(names) > MAX_EXPR_METRICS:
        raise ValueError(
            f"{len(names)} metric names exceeds MAX_EXPR_METRICS ({MAX_EXPR_METRICS})"
        )

    if len(names) == 1:
        metric_part = names[0]
    else:
        # Multiple metrics joined with OR: {m1 or m2 or m3}
        metric_part = "{ " + " or ".join(names) + " }"

    if not host:
        return metric_part

    escaped = _escape_host(host)
    return f'{metric_part} [hostname == "{escaped}"]'


def build_series_exprs(
    names: list[str], host: str = "", chunk_size: int = MAX_EXPR_METRICS
) -> list[str]:
    """Build a list of expressions, chunking names to stay under size limits."""
    if not names:
        return []

    exprs: list[str] = []
    for i in range(0, len(names), chunk_size):
        chunk = names[i : i + chunk_size]
        exprs.append(build_series_expr(chunk, host=host))
    return exprs
