"""Unit tests for pmmcp.tools._stats — _compute_stats, pearson_correlation, outlier_flag."""

from __future__ import annotations

from pmmcp.tools._stats import _compute_stats, outlier_flag, pearson_correlation


class TestComputeStats:
    def test_empty_list_returns_zero_stats(self):
        result = _compute_stats([])
        assert result == {
            "mean": 0.0,
            "min": 0.0,
            "max": 0.0,
            "p95": 0.0,
            "stddev": 0.0,
            "sample_count": 0,
        }

    def test_single_value(self):
        result = _compute_stats([42.0])
        assert result["mean"] == 42.0
        assert result["min"] == 42.0
        assert result["max"] == 42.0
        assert result["p95"] == 42.0
        assert result["stddev"] == 0.0
        assert result["sample_count"] == 1

    def test_uniform_values(self):
        result = _compute_stats([10.0, 10.0, 10.0])
        assert result["mean"] == 10.0
        assert result["stddev"] == 0.0
        assert result["min"] == 10.0
        assert result["max"] == 10.0

    def test_mean_calculation(self):
        result = _compute_stats([1.0, 2.0, 3.0, 4.0, 5.0])
        assert result["mean"] == 3.0

    def test_min_max(self):
        result = _compute_stats([5.0, 1.0, 3.0, 9.0, 2.0])
        assert result["min"] == 1.0
        assert result["max"] == 9.0

    def test_stddev(self):
        # Population stddev of [2, 4, 4, 4, 5, 5, 7, 9] = 2.0
        result = _compute_stats([2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0])
        assert abs(result["stddev"] - 2.0) < 1e-9

    def test_p95_single(self):
        result = _compute_stats([1.0])
        assert result["p95"] == 1.0

    def test_p95_twenty_values(self):
        values = list(range(1, 21))  # 1..20
        result = _compute_stats([float(v) for v in values])
        # 95th percentile of 20 values: ceil(0.95*20) - 1 = 19 - 1 = 18 -> sorted[18] = 19
        assert result["p95"] == 19.0

    def test_sample_count(self):
        result = _compute_stats([1.0, 2.0, 3.0])
        assert result["sample_count"] == 3


class TestPearsonCorrelation:
    def test_perfect_positive_correlation(self):
        xs = [1.0, 2.0, 3.0, 4.0, 5.0]
        ys = [2.0, 4.0, 6.0, 8.0, 10.0]
        r = pearson_correlation(xs, ys)
        assert abs(r - 1.0) < 1e-9

    def test_perfect_negative_correlation(self):
        xs = [1.0, 2.0, 3.0, 4.0, 5.0]
        ys = [10.0, 8.0, 6.0, 4.0, 2.0]
        r = pearson_correlation(xs, ys)
        assert abs(r - (-1.0)) < 1e-9

    def test_zero_correlation_orthogonal(self):
        # Uncorrelated: alternating
        xs = [1.0, -1.0, 1.0, -1.0]
        ys = [1.0, 1.0, -1.0, -1.0]
        r = pearson_correlation(xs, ys)
        assert abs(r) < 1e-9

    def test_zero_variance_x_returns_zero(self):
        xs = [5.0, 5.0, 5.0]
        ys = [1.0, 2.0, 3.0]
        assert pearson_correlation(xs, ys) == 0.0

    def test_zero_variance_y_returns_zero(self):
        xs = [1.0, 2.0, 3.0]
        ys = [7.0, 7.0, 7.0]
        assert pearson_correlation(xs, ys) == 0.0

    def test_empty_returns_zero(self):
        assert pearson_correlation([], []) == 0.0

    def test_single_element_returns_zero(self):
        assert pearson_correlation([1.0], [2.0]) == 0.0

    def test_mismatched_lengths_returns_zero(self):
        assert pearson_correlation([1.0, 2.0], [1.0]) == 0.0

    def test_result_bounded(self):
        import random

        random.seed(42)
        xs = [random.gauss(0, 1) for _ in range(50)]
        ys = [random.gauss(0, 1) for _ in range(50)]
        r = pearson_correlation(xs, ys)
        assert -1.0 <= r <= 1.0


class TestOutlierFlag:
    def test_empty_returns_empty(self):
        assert outlier_flag([]) == []

    def test_single_returns_false(self):
        assert outlier_flag([42.0]) == [False]

    def test_uniform_no_outliers(self):
        assert outlier_flag([5.0, 5.0, 5.0, 5.0]) == [False, False, False, False]

    def test_clear_outlier_flagged(self):
        # 100.0 is far from the cluster around 1.0
        values = [1.0, 1.0, 1.0, 1.0, 1.0, 100.0]
        flags = outlier_flag(values)
        assert flags[-1] is True
        assert all(not f for f in flags[:-1])

    def test_custom_threshold(self):
        # With threshold=1.0, more values should be flagged
        values = [1.0, 2.0, 3.0, 4.0, 10.0]
        flags_2 = outlier_flag(values, threshold=2.0)
        flags_1 = outlier_flag(values, threshold=1.0)
        # Lower threshold catches more outliers
        assert sum(flags_1) >= sum(flags_2)

    def test_zero_stddev_no_outliers(self):
        assert outlier_flag([3.0, 3.0, 3.0]) == [False, False, False]

    def test_returns_parallel_list(self):
        values = [1.0, 2.0, 3.0, 4.0, 100.0]
        flags = outlier_flag(values)
        assert len(flags) == len(values)

    def test_symmetric_outliers(self):
        # Values equally distant from mean should both be flagged
        values = [0.0] * 10 + [100.0, -100.0]
        flags = outlier_flag(values)
        assert flags[-1] is True
        assert flags[-2] is True


class TestExpandTimeUnitsInUtils:
    """Verify _expand_time_units was correctly relocated to utils."""

    def test_expand_minutes(self):
        from pmmcp.utils import expand_time_units

        assert expand_time_units("-2m") == "-2minutes"

    def test_expand_hours(self):
        from pmmcp.utils import expand_time_units

        assert expand_time_units("-1h") == "-1hours"

    def test_expand_seconds(self):
        from pmmcp.utils import expand_time_units

        assert expand_time_units("-30s") == "-30seconds"

    def test_expand_days(self):
        from pmmcp.utils import expand_time_units

        assert expand_time_units("-7d") == "-7days"

    def test_now_unchanged(self):
        from pmmcp.utils import expand_time_units

        assert expand_time_units("now") == "now"

    def test_full_form_unchanged(self):
        from pmmcp.utils import expand_time_units

        assert expand_time_units("-2hours") == "-2hours"

    def test_empty_unchanged(self):
        from pmmcp.utils import expand_time_units

        assert expand_time_units("") == ""
