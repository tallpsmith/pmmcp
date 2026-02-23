import re
from datetime import UTC, datetime, timedelta


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
        r"-(\d+)\s*(s|sec|secs|second|seconds|min|mins|minute|minutes|h|hour|hours|d|day|days|w|week|weeks)",
        expr.strip(),
    )
    if match:
        amount = int(match.group(1))
        unit = match.group(2)
        if unit in ("s", "sec", "secs", "second", "seconds"):
            return now - timedelta(seconds=amount)
        elif unit in ("min", "mins", "minute", "minutes"):
            return now - timedelta(minutes=amount)
        elif unit in ("h", "hour", "hours"):
            return now - timedelta(hours=amount)
        elif unit in ("d", "day", "days"):
            return now - timedelta(days=amount)
        elif unit in ("w", "week", "weeks"):
            return now - timedelta(weeks=amount)

    # ISO-8601 / RFC 3339
    return datetime.fromisoformat(expr.replace("Z", "+00:00"))


def resolve_interval(start: str, end: str, interval: str) -> str:
    """Resolve 'auto' interval to a concrete value based on window duration.

    If interval is not 'auto', returns it unchanged.

    Mapping (per research.md Decision 8):
      <= 1 hour   -> "15s"
      <= 24 hours -> "5min"
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
    elif duration <= 86400:
        return "5min"
    elif duration <= 604800:
        return "1hour"
    else:
        return "6hour"
