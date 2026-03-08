"""Tests for shared series expression builder."""

from __future__ import annotations

import pytest

from pmmcp.tools._expr import MAX_EXPR_METRICS, _escape_host, build_series_expr, build_series_exprs

# ── _escape_host ─────────────────────────────────────────────────────────────


class TestEscapeHost:
    def test_plain_hostname_unchanged(self):
        assert _escape_host("web01.example.com") == "web01.example.com"

    def test_double_quote_escaped(self):
        assert _escape_host('host"name') == 'host\\"name'

    def test_backslash_escaped(self):
        assert _escape_host("host\\name") == "host\\\\name"

    def test_both_escaped(self):
        assert _escape_host('h\\o"st') == 'h\\\\o\\"st'


# ── build_series_expr ────────────────────────────────────────────────────────


class TestBuildSeriesExpr:
    def test_single_metric_no_host(self):
        result = build_series_expr(["kernel.all.load"])
        assert result == "kernel.all.load"

    def test_multiple_metrics_no_host(self):
        result = build_series_expr(["mem.util.used", "mem.util.free"])
        # Multiple metrics joined with OR inside braces
        assert "mem.util.used" in result
        assert "mem.util.free" in result

    def test_single_metric_with_host(self):
        result = build_series_expr(["kernel.all.load"], host="web01")
        assert "kernel.all.load" in result
        assert "web01" in result

    def test_multiple_metrics_with_host(self):
        result = build_series_expr(["mem.util.used", "mem.util.free"], host="web01")
        assert "mem.util.used" in result
        assert "mem.util.free" in result
        assert "web01" in result

    def test_host_with_quotes_escaped(self):
        result = build_series_expr(["kernel.all.load"], host='host"evil')
        # The raw double-quote must be escaped in the output
        assert '\\"' in result
        assert 'host"evil' not in result

    def test_too_many_metrics_raises(self):
        names = [f"metric.name.{i}" for i in range(MAX_EXPR_METRICS + 1)]
        with pytest.raises(ValueError, match="exceeds.*MAX_EXPR_METRICS"):
            build_series_expr(names)

    def test_exactly_max_metrics_ok(self):
        names = [f"metric.name.{i}" for i in range(MAX_EXPR_METRICS)]
        # Should not raise
        result = build_series_expr(names)
        assert "metric.name.0" in result


# ── build_series_exprs ───────────────────────────────────────────────────────


class TestBuildSeriesExprs:
    def test_small_list_single_expression(self):
        names = ["a", "b", "c"]
        exprs = build_series_exprs(names)
        assert len(exprs) == 1

    def test_chunks_at_boundary(self):
        """Names list exceeding chunk_size produces multiple expressions."""
        names = [f"m.{i}" for i in range(MAX_EXPR_METRICS + 10)]
        exprs = build_series_exprs(names)
        assert len(exprs) == 2

    def test_exact_chunk_size_single_expression(self):
        names = [f"m.{i}" for i in range(MAX_EXPR_METRICS)]
        exprs = build_series_exprs(names)
        assert len(exprs) == 1

    def test_custom_chunk_size(self):
        names = ["a", "b", "c", "d", "e"]
        exprs = build_series_exprs(names, chunk_size=2)
        assert len(exprs) == 3  # 2 + 2 + 1

    def test_host_propagated_to_all_chunks(self):
        names = ["a", "b", "c"]
        exprs = build_series_exprs(names, host="web01", chunk_size=2)
        for expr in exprs:
            assert "web01" in expr

    def test_empty_list_returns_empty(self):
        assert build_series_exprs([]) == []
