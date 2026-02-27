import math
import re
from datetime import UTC, datetime, timedelta

_SHORT_UNIT_MAP = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days", "w": "weeks"}


def expand_time_units(expr: str) -> str:
    """Expand abbreviated time units to full forms pmproxy's series API accepts.

    Converts e.g. '-2m' to '-2minutes', '-1h' to '-1hours'.
    Leaves 'now', full-form expressions, and ISO timestamps unchanged.
    """
    if expr in ("now", ""):
        return expr
    match = re.fullmatch(r"(-\d+)\s*([smhdw])$", expr.strip())
    if match:
        n, unit = match.group(1), match.group(2)
        return f"{n}{_SHORT_UNIT_MAP[unit]}"
    return expr


def parse_time_expr(expr: str, _now: datetime | None = None) -> datetime:
    """Parse a PCP relative time expression or ISO-8601 timestamp to datetime.

    Handles:
    - PCP relative: "-6hours", "-7days", "-30min", "-1hour", "-2weeks"
    - ISO-8601 absolute: "2024-01-15T10:30:00Z"
    - "now"

    The optional _now parameter pins the reference time (for deterministic testing).
    """
    now = _now if _now is not None else datetime.now(tz=UTC)

    if expr == "now":
        return now

    # PCP relative expression: e.g. "-6hours", "-30min", "-7days"
    match = re.fullmatch(
        r"-(\d+)\s*(s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hour|hours|d|day|days|w|week|weeks)",
        expr.strip(),
    )
    if match:
        amount = int(match.group(1))
        unit = match.group(2)
        if unit in ("s", "sec", "secs", "second", "seconds"):
            return now - timedelta(seconds=amount)
        elif unit in ("m", "min", "mins", "minute", "minutes"):
            return now - timedelta(minutes=amount)
        elif unit in ("h", "hour", "hours"):
            return now - timedelta(hours=amount)
        elif unit in ("d", "day", "days"):
            return now - timedelta(days=amount)
        elif unit in ("w", "week", "weeks"):
            return now - timedelta(weeks=amount)

    # ISO-8601 / RFC 3339
    return datetime.fromisoformat(expr.replace("Z", "+00:00"))


def interval_to_seconds(interval: str) -> float:
    """Convert an interval string (e.g. '15s', '5min', '1hour', '6hour') to seconds."""
    match = re.fullmatch(
        r"(\d+(?:\.\d+)?)\s*(s|sec|secs|second|seconds|min|mins|minute|minutes|h|hour|hours|d|day|days)",
        interval.strip(),
    )
    if not match:
        raise ValueError(f"Cannot parse interval: {interval!r}")
    amount = float(match.group(1))
    unit = match.group(2)
    if unit in ("s", "sec", "secs", "second", "seconds"):
        return amount
    elif unit in ("min", "mins", "minute", "minutes"):
        return amount * 60
    elif unit in ("h", "hour", "hours"):
        return amount * 3600
    elif unit in ("d", "day", "days"):
        return amount * 86400
    raise ValueError(f"Unknown unit: {unit!r}")  # pragma: no cover


def natural_samples(start: str, end: str, resolved_interval: str) -> int:
    """Compute how many samples naturally fit in the window given the interval."""
    ref = datetime.now(tz=UTC)
    start_dt = parse_time_expr(start, _now=ref)
    end_dt = parse_time_expr(end, _now=ref)
    window_secs = (end_dt - start_dt).total_seconds()
    interval_secs = interval_to_seconds(resolved_interval)
    return max(1, math.ceil(window_secs / interval_secs))


def resolve_interval(start: str, end: str, interval: str) -> str:
    """Resolve 'auto' interval to a concrete value based on window duration.

    If interval is not 'auto', returns it unchanged.

    Mapping:
      <= 1 hour   -> "15s"
      <= 6 hours  -> "5min"
      <= 24 hours -> "15min"
      <= 7 days   -> "1hour"
      > 7 days    -> "6hour"
    """
    if interval != "auto":
        return interval

    # Use a shared reference time so relative expressions are consistent
    ref_now = datetime.now(tz=UTC)
    start_dt = parse_time_expr(start, _now=ref_now)
    end_dt = parse_time_expr(end, _now=ref_now)
    duration = (end_dt - start_dt).total_seconds()

    if duration <= 3600:
        return "15s"
    elif duration <= 21600:
        return "5min"
    elif duration <= 86400:
        return "15min"
    elif duration <= 604800:
        return "1hour"
    else:
        return "6hour"
