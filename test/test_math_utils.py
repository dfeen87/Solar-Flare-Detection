"""
test_math_utils.py — Unit tests for shared/math_utils.py.

Covers every public function:
  rolling_variance, normalize_01, euv_derivative, rolling_correlation,
  classify_regime, compute_chi, compute_delta_phi, compute_composite_indicator.
"""

import math
import numpy as np
import pytest

from shared.math_utils import (
    rolling_variance,
    normalize_01,
    euv_derivative,
    rolling_correlation,
    classify_regime,
    compute_chi,
    compute_delta_phi,
    compute_composite_indicator,
)

# ===========================================================================
# rolling_variance — PAPER.md Eq. (3)
# ===========================================================================


class TestRollingVariance:
    def test_constant_series_zero_variance(self):
        """Constant series → variance is 0 for all valid windows."""
        series = np.full(10, 5.0)
        result = rolling_variance(series, L=3)
        assert np.all(result[2:] == 0.0)

    def test_first_L_minus_1_are_nan(self):
        """First L-1 values must be NaN."""
        series = np.arange(10, dtype=float)
        L = 4
        result = rolling_variance(series, L=L)
        assert np.all(np.isnan(result[: L - 1]))

    def test_output_length_matches_input(self):
        """Output length must equal input length."""
        series = np.random.default_rng(0).random(20)
        result = rolling_variance(series, L=5)
        assert len(result) == len(series)

    def test_known_values_window2(self):
        """Window=2 on [0, 1, 0, 1] — manually verified expected values."""
        series = np.array([0.0, 1.0, 0.0, 1.0])
        result = rolling_variance(series, L=2)
        # First value NaN
        assert np.isnan(result[0])
        # Each window of size 2: variance = 0.25
        expected = 0.25
        np.testing.assert_allclose(result[1:], expected)

    def test_window_1_returns_zeros(self):
        """Window of 1 → every point is its own mean, variance = 0."""
        series = np.array([3.0, 1.0, 4.0, 1.0])
        result = rolling_variance(series, L=1)
        np.testing.assert_array_equal(result, np.zeros(4))


# ===========================================================================
# normalize_01
# ===========================================================================


class TestNormalize01:
    def test_all_identical_returns_zeros(self):
        """All-identical array → all zeros."""
        arr = np.full(5, 7.0)
        result = normalize_01(arr)
        np.testing.assert_array_equal(result, np.zeros(5))

    def test_known_input(self):
        """[0, 5, 10] → [0.0, 0.5, 1.0]."""
        arr = np.array([0.0, 5.0, 10.0])
        result = normalize_01(arr)
        np.testing.assert_allclose(result, [0.0, 0.5, 1.0])

    def test_nan_stays_nan(self):
        """NaN values remain NaN; valid values are normalized correctly."""
        arr = np.array([0.0, np.nan, 10.0])
        result = normalize_01(arr)
        assert np.isnan(result[1])
        np.testing.assert_allclose(result[[0, 2]], [0.0, 1.0])

    def test_min_is_zero_max_is_one(self):
        """After normalization min→0 and max→1 (ignoring NaN)."""
        arr = np.array([3.0, 1.0, 4.0, 1.0, 5.0])
        result = normalize_01(arr)
        assert np.nanmin(result) == pytest.approx(0.0)
        assert np.nanmax(result) == pytest.approx(1.0)


# ===========================================================================
# euv_derivative — PAPER.md Eq. (5) third term
# ===========================================================================


class TestEuvDerivative:
    def test_constant_series_zero_derivative(self):
        """Constant EUV → absolute derivative is 0 everywhere."""
        euv = np.full(10, 3.14)
        result = euv_derivative(euv)
        np.testing.assert_allclose(result, np.zeros(10), atol=1e-12)

    def test_linear_ramp_constant_derivative(self):
        """Linear ramp y=x → |dy/dx| = 1 everywhere (central differences)."""
        euv = np.arange(10, dtype=float)
        result = euv_derivative(euv)
        # np.gradient gives 1 at all interior points; endpoints also 1 for uniform step
        np.testing.assert_allclose(result, np.ones(10), atol=1e-12)

    def test_output_length_matches_input(self):
        """Output length must equal input length."""
        euv = np.random.default_rng(1).random(15)
        result = euv_derivative(euv)
        assert len(result) == len(euv)

    def test_nonnegative(self):
        """Absolute derivative is always ≥ 0."""
        euv = np.random.default_rng(2).random(20)
        assert np.all(euv_derivative(euv) >= 0)


# ===========================================================================
# rolling_correlation — PAPER.md §6.2 C(t)
# ===========================================================================


class TestRollingCorrelation:
    def test_perfectly_correlated_signals(self):
        """Identical signals → correlation ≈ 1 for all valid windows."""
        x = np.random.default_rng(3).random(20)
        result = rolling_correlation(x, x.copy(), L=5)
        np.testing.assert_allclose(result[4:], 1.0, atol=1e-10)

    def test_anti_correlated_signals(self):
        """Negated signal → correlation ≈ -1 for all valid windows."""
        x = np.random.default_rng(4).random(20)
        result = rolling_correlation(x, -x, L=5)
        np.testing.assert_allclose(result[4:], -1.0, atol=1e-10)

    def test_constant_signal_zero_correlation(self):
        """One constant signal → std=0, correlation set to 0."""
        x = np.arange(10, dtype=float)
        y = np.full(10, 2.0)
        result = rolling_correlation(x, y, L=3)
        np.testing.assert_array_equal(result[2:], 0.0)

    def test_first_L_minus_1_are_nan(self):
        """First L-1 values must be NaN."""
        x = np.arange(10, dtype=float)
        L = 4
        result = rolling_correlation(x, x, L=L)
        assert np.all(np.isnan(result[: L - 1]))

    def test_output_length_matches_input(self):
        """Output length must equal input length."""
        x = np.random.default_rng(5).random(25)
        result = rolling_correlation(x, x, L=6)
        assert len(result) == len(x)


# ===========================================================================
# classify_regime — PAPER.md §6.4
# ===========================================================================


class TestClassifyRegime:
    def test_zero_is_isostasis(self):
        assert classify_regime(0.0) == "Isostasis"

    def test_just_below_first_threshold(self):
        assert classify_regime(0.14) == "Isostasis"

    def test_at_first_threshold(self):
        assert classify_regime(0.15) == "Allostasis"

    def test_mid_allostasis(self):
        assert classify_regime(0.25) == "Allostasis"

    def test_just_below_second_threshold(self):
        assert classify_regime(0.34) == "Allostasis"

    def test_at_second_threshold(self):
        assert classify_regime(0.35) == "High-Allostasis"

    def test_just_below_third_threshold(self):
        assert classify_regime(0.39) == "High-Allostasis"

    def test_at_third_threshold_is_collapse(self):
        assert classify_regime(0.40) == "Collapse"

    def test_one_is_collapse(self):
        assert classify_regime(1.0) == "Collapse"

    def test_all_four_labels_reachable(self):
        labels = {classify_regime(v) for v in [0.0, 0.2, 0.37, 0.5]}
        assert labels == {"Isostasis", "Allostasis", "High-Allostasis", "Collapse"}


# ===========================================================================
# compute_chi — PAPER.md §6.3
# ===========================================================================


class TestComputeChi:
    def test_all_zero_variance_chi_stays_zero(self):
        """Var_B = 0 (after NaN region) → chi stays 0."""
        var_b = np.array([np.nan, np.nan, 0.0, 0.0, 0.0])
        result = compute_chi(var_b, window_L=3)
        np.testing.assert_array_equal(result[2:], 0.0)

    def test_nan_masked_at_start(self):
        """First window_L-1 values must be NaN."""
        var_b = np.array([np.nan, np.nan, 1.0, 1.0, 1.0])
        result = compute_chi(var_b, window_L=3)
        assert np.all(np.isnan(result[:2]))

    def test_constant_variance_chi_grows_linearly(self):
        """Constant variance c → chi = cumsum = 0, c, 2c, 3c … (after NaN region)."""
        c = 2.0
        var_b = np.array([np.nan, c, c, c, c])
        result = compute_chi(var_b, window_L=2)
        # cumsum of [0, c, c, c, c] skipping initial NaN → [c, 2c, 3c, 4c]
        np.testing.assert_allclose(result[1:], [c, 2 * c, 3 * c, 4 * c])

    def test_output_length_matches_input(self):
        var_b = rolling_variance(np.arange(10, dtype=float), L=3)
        result = compute_chi(var_b, window_L=3)
        assert len(result) == len(var_b)


# ===========================================================================
# compute_delta_phi — PAPER.md Eq. (6)
# ===========================================================================


class TestComputeDeltaPhi:
    def test_constant_inputs_zero_after_nan(self):
        """Constant S, I, C → ΔΦ = 0 for all t > 0."""
        S = np.full(10, 1.0)
        I = np.full(10, 2.0)
        C = np.full(10, 0.5)
        result = compute_delta_phi(S, I, C)
        assert np.isnan(result[0])
        np.testing.assert_allclose(result[1:], 0.0, atol=1e-15)

    def test_step_in_S_only(self):
        """Step of size 1 in S at index 3 → ΔΦ[3] = alpha * 1."""
        alpha = 1 / 3
        S = np.array([0.0, 0.0, 0.0, 1.0, 1.0, 1.0])
        I = np.zeros(6)
        C = np.zeros(6)
        result = compute_delta_phi(S, I, C, alpha=alpha, beta=0.0, gamma=0.0)
        assert np.isnan(result[0])
        np.testing.assert_allclose(result[3], alpha, atol=1e-15)
        # Other valid steps are 0
        np.testing.assert_allclose(result[[1, 2, 4, 5]], 0.0, atol=1e-15)

    def test_custom_weights(self):
        """Custom weights: only beta non-zero → result = beta * |ΔI|."""
        S = np.zeros(5)
        I = np.array([0.0, 2.0, 2.0, 2.0, 2.0])
        C = np.zeros(5)
        beta = 0.5
        result = compute_delta_phi(S, I, C, alpha=0.0, beta=beta, gamma=0.0)
        assert np.isnan(result[0])
        np.testing.assert_allclose(result[1], beta * 2.0, atol=1e-15)
        np.testing.assert_allclose(result[2:], 0.0, atol=1e-15)

    def test_output_length_matches_input(self):
        """Output length must equal input length."""
        n = 20
        S = np.random.default_rng(6).random(n)
        I = np.random.default_rng(7).random(n)
        C = np.random.default_rng(8).random(n)
        result = compute_delta_phi(S, I, C)
        assert len(result) == n

    def test_first_element_is_nan(self):
        """First element must always be NaN."""
        S = np.arange(5, dtype=float)
        I = np.arange(5, dtype=float)
        C = np.arange(5, dtype=float)
        result = compute_delta_phi(S, I, C)
        assert np.isnan(result[0])

    def test_equal_weights_sum_to_one_third_each(self):
        """Default 1/3 weights: step of 3 in all channels → ΔΦ = 3."""
        S = np.array([0.0, 3.0])
        I = np.array([0.0, 3.0])
        C = np.array([0.0, 3.0])
        result = compute_delta_phi(S, I, C)
        np.testing.assert_allclose(result[1], 3.0, atol=1e-14)


# ===========================================================================
# compute_composite_indicator — PAPER.md Eq. (5)
# ===========================================================================


class TestComputeCompositeIndicator:
    def test_equal_inputs_equal_weights_returns_input(self):
        """All three inputs identical, equal weights → output equals input."""
        x = np.array([0.0, 0.25, 0.5, 0.75, 1.0])
        result = compute_composite_indicator(x, x, x)
        np.testing.assert_allclose(result, x, atol=1e-14)

    def test_zero_inputs_zero_output(self):
        """All-zero inputs → all-zero output."""
        zeros = np.zeros(8)
        result = compute_composite_indicator(zeros, zeros, zeros)
        np.testing.assert_array_equal(result, zeros)

    def test_custom_weights_sum(self):
        """w1=0.5, w2=0.3, w3=0.2: known sum on unit vectors."""
        a = np.array([1.0, 0.0, 0.0])
        b = np.array([0.0, 1.0, 0.0])
        c = np.array([0.0, 0.0, 1.0])
        result = compute_composite_indicator(a, b, c, w1=0.5, w2=0.3, w3=0.2)
        np.testing.assert_allclose(result, [0.5, 0.3, 0.2], atol=1e-14)

    def test_output_length_matches_input(self):
        """Output length must equal input length."""
        n = 12
        x = np.random.default_rng(9).random(n)
        result = compute_composite_indicator(x, x, x)
        assert len(result) == n

    def test_single_nonzero_channel(self):
        """Only w2 channel active → result = w2 * var_b_norm."""
        zeros = np.zeros(5)
        var_b = np.array([0.1, 0.2, 0.3, 0.4, 0.5])
        w2 = 0.7
        result = compute_composite_indicator(zeros, var_b, zeros, w1=0.0, w2=w2, w3=0.0)
        np.testing.assert_allclose(result, w2 * var_b, atol=1e-14)
