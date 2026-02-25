"""Unit tests for pmmcp.utils — resolve_interval and parse_time_expr."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pmmcp.utils import interval_to_seconds, natural_samples, parse_time_expr, resolve_interval


class TestResolveInterval:
    def test_explicit_interval_passthrough(self):
        assert resolve_interval("-1hour", "now", "15s") == "15s"
        assert resolve_interval("-1hour", "now", "5min") == "5min"
        assert resolve_interval("-1hour", "now", "1hour") == "1hour"
        assert resolve_interval("-1hour", "now", "6hour") == "6hour"

    def test_auto_le_1_hour(self):
        assert resolve_interval("-1hour", "now", "auto") == "15s"
        assert resolve_interval("-30min", "now", "auto") == "15s"
        # Exactly 1 hour (3600s boundary)
        assert resolve_interval("-1hour", "now", "auto") == "15s"

    def test_auto_le_6_hours(self):
        assert resolve_interval("-2hours", "now", "auto") == "5min"
        assert resolve_interval("-6hours", "now", "auto") == "5min"

    def test_auto_le_24_hours(self):
        assert resolve_interval("-7hours", "now", "auto") == "15min"
        assert resolve_interval("-12hours", "now", "auto") == "15min"
        assert resolve_interval("-24hours", "now", "auto") == "15min"

    def test_auto_le_7_days(self):
        assert resolve_interval("-2days", "now", "auto") == "1hour"
        assert resolve_interval("-7days", "now", "auto") == "1hour"

    def test_auto_gt_7_days(self):
        assert resolve_interval("-8days", "now", "auto") == "6hour"
        assert resolve_interval("-30days", "now", "auto") == "6hour"

    def test_boundary_3600s(self):
        # 3600s exactly -> "15s"
        assert resolve_interval("-1hour", "now", "auto") == "15s"
        # just over 1 hour -> "5min"
        assert resolve_interval("-61min", "now", "auto") == "5min"

    def test_boundary_21600s(self):
        # 6 hours exactly -> "5min"
        assert resolve_interval("-6hours", "now", "auto") == "5min"
        # just over 6 hours -> "15min"
        assert resolve_interval("-361min", "now", "auto") == "15min"

    def test_boundary_86400s(self):
        # 24 hours exactly -> "15min"
        assert resolve_interval("-24hours", "now", "auto") == "15min"
        # 25 hours -> "1hour"
        assert resolve_interval("-25hours", "now", "auto") == "1hour"

    def test_boundary_604800s(self):
        # 7 days exactly -> "1hour"
        assert resolve_interval("-7days", "now", "auto") == "1hour"
        # 8 days -> "6hour"
        assert resolve_interval("-8days", "now", "auto") == "6hour"


class TestParseTimeExpr:
    def test_now(self):
        result = parse_time_expr("now")
        assert isinstance(result, datetime)
        assert result.tzinfo == UTC

    def test_relative_hours(self):
        result = parse_time_expr("-1hour")
        now = datetime.now(tz=UTC)
        diff = (now - result).total_seconds()
        assert 3500 < diff < 3700  # ~3600s

    def test_relative_hours_plural(self):
        result = parse_time_expr("-6hours")
        now = datetime.now(tz=UTC)
        diff = (now - result).total_seconds()
        assert 21500 < diff < 21700  # ~21600s

    def test_relative_minutes(self):
        result = parse_time_expr("-30min")
        now = datetime.now(tz=UTC)
        diff = (now - result).total_seconds()
        assert 1750 < diff < 1850  # ~1800s

    def test_relative_days(self):
        result = parse_time_expr("-7days")
        now = datetime.now(tz=UTC)
        diff = (now - result).total_seconds()
        assert 7 * 86400 - 100 < diff < 7 * 86400 + 100

    def test_relative_seconds(self):
        result = parse_time_expr("-60s")
        now = datetime.now(tz=UTC)
        diff = (now - result).total_seconds()
        assert 55 < diff < 65

    def test_relative_weeks(self):
        result = parse_time_expr("-2weeks")
        now = datetime.now(tz=UTC)
        diff = (now - result).total_seconds()
        assert 2 * 7 * 86400 - 100 < diff < 2 * 7 * 86400 + 100

    def test_iso8601_with_z(self):
        result = parse_time_expr("2024-01-15T10:30:00Z")
        assert result == datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)

    def test_iso8601_with_offset(self):
        result = parse_time_expr("2024-01-15T10:30:00+00:00")
        assert result == datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)

    def test_invalid_iso8601_raises(self):
        with pytest.raises((ValueError, Exception)):
            parse_time_expr("not-a-date")


class TestIntervalToSeconds:
    def test_seconds(self):
        assert interval_to_seconds("15s") == 15.0
        assert interval_to_seconds("1second") == 1.0
        assert interval_to_seconds("60secs") == 60.0

    def test_minutes(self):
        assert interval_to_seconds("5min") == 300.0
        assert interval_to_seconds("1minute") == 60.0

    def test_hours(self):
        assert interval_to_seconds("1hour") == 3600.0
        assert interval_to_seconds("6hour") == 21600.0
        assert interval_to_seconds("1h") == 3600.0

    def test_days(self):
        assert interval_to_seconds("1day") == 86400.0
        assert interval_to_seconds("7days") == 7 * 86400.0

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            interval_to_seconds("auto")

        with pytest.raises(ValueError):
            interval_to_seconds("not-an-interval")


class TestNaturalSamples:
    def test_1hour_at_15s(self):
        # 3600 / 15 = 240
        assert natural_samples("-1hour", "now", "15s") == 240

    def test_24hours_at_5min(self):
        # 86400 / 300 = 288
        assert natural_samples("-24hours", "now", "5min") == 288

    def test_7days_at_1hour(self):
        # 604800 / 3600 = 168
        assert natural_samples("-7days", "now", "1hour") == 168

    def test_30days_at_6hour(self):
        # 2592000 / 21600 = 120
        assert natural_samples("-30days", "now", "6hour") == 120

    def test_minimum_is_one(self):
        # Very short window
        assert natural_samples("-1s", "now", "1hour") == 1
