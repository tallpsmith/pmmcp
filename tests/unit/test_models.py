"""Unit tests for pmmcp.models — Pydantic model validation (T041 coverage)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from pmmcp.models import (
    DeltaStats,
    Host,
    Instance,
    Metric,
    MetricValue,
    PaginatedResponse,
    SearchResult,
    TimeWindow,
    WindowComparison,
    WindowStats,
)


class TestHost:
    def test_host_basic(self):
        h = Host(source="abc123", hostnames=["web-01.example.com"])
        assert h.source == "abc123"
        assert h.hostnames == ["web-01.example.com"]
        assert h.labels == {}

    def test_host_with_labels(self):
        h = Host(source="abc", hostnames=["web-01"], labels={"platform": "linux"})
        assert h.labels["platform"] == "linux"

    def test_host_multiple_hostnames(self):
        h = Host(source="abc", hostnames=["web-01", "192.168.1.1"])
        assert len(h.hostnames) == 2


class TestMetric:
    def test_metric_basic(self):
        m = Metric(
            name="kernel.all.load",
            pmid="60.2.0",
            type="float",
            semantics="instant",
            units="none",
        )
        assert m.name == "kernel.all.load"
        assert m.indom is None
        assert m.series == ""
        assert m.oneline == ""
        assert m.helptext == ""

    def test_metric_with_indom(self):
        m = Metric(
            name="disk.dev.read",
            pmid="60.0.4",
            type="u32",
            semantics="counter",
            units="count",
            indom="60.1",
        )
        assert m.indom == "60.1"

    def test_metric_invalid_name(self):
        with pytest.raises(ValidationError):
            Metric(
                name="invalid name with spaces",
                pmid="1.0.0",
                type="u32",
                semantics="instant",
                units="count",
            )

    def test_metric_full_fields(self):
        m = Metric(
            name="kernel.all.cpu.user",
            pmid="60.0.20",
            type="u32",
            semantics="counter",
            units="millisec",
            indom=None,
            series="abc123",
            source="src123",
            labels={"hostname": "localhost"},
            oneline="CPU user time",
            helptext="Time the CPU has spent executing user-space processes",
        )
        assert m.oneline == "CPU user time"
        assert m.labels["hostname"] == "localhost"


class TestInstance:
    def test_instance_basic(self):
        i = Instance(instance=0, name="sda")
        assert i.instance == 0
        assert i.name == "sda"
        assert i.series == ""
        assert i.labels == {}

    def test_instance_with_labels(self):
        i = Instance(instance=1, name="sdb", labels={"type": "nvme"})
        assert i.labels["type"] == "nvme"


class TestMetricValue:
    def test_metric_value_string(self):
        mv = MetricValue(series="abc", timestamp=1547483646000000000, value="42.5")
        assert mv.value == "42.5"
        assert mv.instance is None

    def test_metric_value_float(self):
        mv = MetricValue(series="abc", timestamp=1547483646000000000, value=3.14)
        assert mv.value == 3.14

    def test_metric_value_with_instance(self):
        mv = MetricValue(series="abc", timestamp=1547483646000000000, value=100, instance="sda")
        assert mv.instance == "sda"


class TestTimeWindow:
    def test_default_values(self):
        tw = TimeWindow()
        assert tw.start == "-1hour"
        assert tw.end == "now"
        assert tw.interval == "auto"

    def test_custom_values(self):
        tw = TimeWindow(start="-7days", end="now", interval="1hour")
        assert tw.start == "-7days"
        assert tw.interval == "1hour"


class TestWindowStats:
    def test_window_stats(self):
        ws = WindowStats(mean=50.0, min=10.0, max=90.0, p95=85.0, stddev=15.0, sample_count=100)
        assert ws.mean == 50.0
        assert ws.p95 == 85.0
        assert ws.sample_count == 100


class TestDeltaStats:
    def test_significant(self):
        d = DeltaStats(mean_change=30.0, mean_change_pct=60.0, stddev_change=5.0, significant=True)
        assert d.significant is True

    def test_not_significant(self):
        d = DeltaStats(mean_change=0.5, mean_change_pct=1.0, stddev_change=0.1, significant=False)
        assert d.significant is False


class TestWindowComparison:
    def test_window_comparison(self):
        wa = WindowStats(mean=10.0, min=5.0, max=15.0, p95=14.0, stddev=2.0, sample_count=10)
        wb = WindowStats(mean=50.0, min=40.0, max=60.0, p95=58.0, stddev=5.0, sample_count=10)
        delta = DeltaStats(
            mean_change=40.0, mean_change_pct=400.0, stddev_change=3.0, significant=True
        )
        wc = WindowComparison(metric="kernel.all.cpu.user", window_a=wa, window_b=wb, delta=delta)
        assert wc.metric == "kernel.all.cpu.user"
        assert wc.instance is None
        assert wc.delta.significant is True

    def test_window_comparison_with_instance(self):
        wa = WindowStats(mean=10.0, min=5.0, max=15.0, p95=14.0, stddev=2.0, sample_count=5)
        wb = WindowStats(mean=12.0, min=6.0, max=18.0, p95=17.0, stddev=3.0, sample_count=5)
        delta = DeltaStats(
            mean_change=2.0, mean_change_pct=20.0, stddev_change=1.0, significant=False
        )
        wc = WindowComparison(
            metric="disk.dev.read", instance="sda", window_a=wa, window_b=wb, delta=delta
        )
        assert wc.instance == "sda"


class TestSearchResult:
    def test_search_result_basic(self):
        sr = SearchResult(name="kernel.all.load", type="metric")
        assert sr.name == "kernel.all.load"
        assert sr.oneline == ""
        assert sr.helptext == ""
        assert sr.score == 0.0

    def test_search_result_full(self):
        sr = SearchResult(
            name="mem.util.free",
            type="metric",
            oneline="Free memory",
            helptext="Extended help text",
            score=0.95,
        )
        assert sr.score == 0.95


class TestPaginatedResponse:
    def test_paginated_response(self):
        pr = PaginatedResponse[Host](
            items=[Host(source="abc", hostnames=["web-01"])],
            total=1,
            limit=50,
            offset=0,
            has_more=False,
        )
        assert len(pr.items) == 1
        assert pr.has_more is False

    def test_paginated_response_has_more(self):
        pr = PaginatedResponse[Host](
            items=[Host(source="abc", hostnames=["web-01"])],
            total=100,
            limit=1,
            offset=0,
            has_more=True,
        )
        assert pr.has_more is True

    def test_paginated_response_limit_validation(self):
        with pytest.raises(ValidationError):
            PaginatedResponse[Host](items=[], total=0, limit=0, offset=0, has_more=False)

    def test_paginated_response_offset_validation(self):
        with pytest.raises(ValidationError):
            PaginatedResponse[Host](items=[], total=0, limit=10, offset=-1, has_more=False)
