import pytest

from merf.stats import compute_stats


class TestMedian:
    def test_middle_value_for_odd_count(self) -> None:
        result = compute_stats([0.1, 0.2, 0.3, 0.4, 0.5])
        assert result.median == pytest.approx(0.3)

    def test_average_of_two_middles_for_even_count(self) -> None:
        result = compute_stats([0.1, 0.2, 0.3, 0.4])
        assert result.median == pytest.approx(0.25)

    def test_order_independent(self) -> None:
        # Unsorted input must give the same median as sorted
        result = compute_stats([0.5, 0.1, 0.3, 0.2, 0.4])
        assert result.median == pytest.approx(0.3)

    def test_identical_samples(self) -> None:
        result = compute_stats([0.42, 0.42, 0.42, 0.42, 0.42])
        assert result.median == pytest.approx(0.42)


class TestP95:
    def test_interpolates_for_small_n(self) -> None:
        # index = 0.95 * (5-1) = 3.8 → 0.4 * 0.2 + 0.5 * 0.8 = 0.48
        # With interpolation p95 is between the top two values, not the maximum.
        samples = [0.1, 0.2, 0.3, 0.4, 0.5]
        result = compute_stats(samples)
        assert result.p95 == pytest.approx(0.48)

    def test_interpolated_value_for_20_samples(self) -> None:
        # index = 0.95 * (20-1) = 18.05 → 0.19 * 0.95 + 0.20 * 0.05 = 0.1905
        samples = [i * 0.01 for i in range(1, 21)]  # [0.01, 0.02, ..., 0.20]
        result = compute_stats(samples)
        assert result.p95 == pytest.approx(0.1905)

    def test_exceeds_median_for_right_skewed_data(self) -> None:
        # 18 fast runs with 2 slow outliers — p95 should capture the outliers,
        # while the median stays near the fast cluster
        samples = [0.1] * 18 + [0.9, 1.0]
        result = compute_stats(samples)
        assert result.p95 > result.median

    def test_equals_median_when_all_samples_identical(self) -> None:
        result = compute_stats([0.5] * 10)
        assert result.p95 == pytest.approx(result.median)


class TestPurity:
    def test_does_not_mutate_input(self) -> None:
        # Sorting is a common implementation detail that mutates the list in-place;
        # compute_stats must work on a copy
        samples = [0.3, 0.1, 0.2, 0.4, 0.5]
        original = samples.copy()
        compute_stats(samples)
        assert samples == original
