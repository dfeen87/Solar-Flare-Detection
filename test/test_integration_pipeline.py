"""
test_integration_pipeline.py — Integration test for the full PAPER.md pipeline.

Exercises the complete scientific pipeline end-to-end using synthetic data so
that no network connection is required:

    synthetic data
        → rolling_variance  → Var_L[X], Var_L[B]
        → euv_derivative    → |d/dt EUV|
        → normalize_01      → normalized components
        → compute_composite_indicator → I(t)
        → rolling_correlation → C(t)
        → compute_delta_phi  → ΔΦ(t)
        → normalize_01       → ΔΦ_norm
        → classify_regime    → regime label
        → compute_chi        → χ(t)
        → plot_delta_phi     → (fig, ax)
        → plot_psi_trajectory → (fig, ax)
        → plot_composite_indicator → (fig, ax)

All assertions are made against the final outputs to confirm correctness of the
full chain.  Figures are closed immediately after smoke-testing to avoid memory
leaks in CI.
"""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pytest

from shared.math_utils import (
    REGIME_LABELS,
    rolling_variance,
    normalize_01,
    euv_derivative,
    rolling_correlation,
    compute_composite_indicator,
    compute_delta_phi,
    classify_regime,
    compute_chi,
)
from shared.plot_utils import (
    plot_delta_phi,
    plot_psi_trajectory,
    plot_composite_indicator,
)

# ---------------------------------------------------------------------------
# Synthetic data generation helpers
# ---------------------------------------------------------------------------

#: Number of time steps in the synthetic data.
_N: int = 200

#: Rolling-window length used throughout the pipeline.
_L: int = 20


@pytest.fixture(scope="module")
def synthetic_times():
    """Evenly-spaced numeric time axis [0, 1)."""
    return np.linspace(0.0, 1.0, _N)


@pytest.fixture(scope="module")
def synthetic_xray(synthetic_times):
    """X-ray flux with a simulated flare bump near t=0.6."""
    rng = np.random.default_rng(0)
    base = np.full(_N, 1e-7)
    bump = 5e-7 * np.exp(-((synthetic_times - 0.6) ** 2) / (2 * 0.01**2))
    noise = rng.standard_normal(_N) * 5e-9
    return np.abs(base + bump + noise)


@pytest.fixture(scope="module")
def synthetic_magnetometer(synthetic_times):
    """Magnetometer signal with correlated variance increase near the flare."""
    rng = np.random.default_rng(1)
    base = np.sin(2 * np.pi * 3 * synthetic_times)
    variance_ramp = 0.3 * np.clip(synthetic_times - 0.5, 0, None)
    noise = rng.standard_normal(_N) * 0.05
    return base + variance_ramp * rng.standard_normal(_N) + noise


@pytest.fixture(scope="module")
def synthetic_euv(synthetic_times):
    """EUV irradiance with a gradual rise before the flare peak."""
    rng = np.random.default_rng(2)
    trend = 1.0 + 0.5 * np.clip(synthetic_times - 0.4, 0, None)
    noise = rng.standard_normal(_N) * 0.02
    return trend + noise


# ---------------------------------------------------------------------------
# Full pipeline fixture — computes all intermediate products once per session.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def pipeline_outputs(synthetic_xray, synthetic_magnetometer, synthetic_euv):
    """Run the complete PAPER.md pipeline and return all intermediate results."""
    X = synthetic_xray
    B = synthetic_magnetometer
    EUV = synthetic_euv

    # Step 1–2 — Rolling variance
    var_x = rolling_variance(X, _L)
    var_b = rolling_variance(B, _L)

    # Step 3 — EUV derivative
    d_euv = euv_derivative(EUV)

    # Step 4 — Normalize each component
    var_x_norm = normalize_01(var_x)
    var_b_norm = normalize_01(var_b)
    d_euv_norm = normalize_01(d_euv)

    # Step 5 — Composite indicator I(t)
    indicator = compute_composite_indicator(var_x_norm, var_b_norm, d_euv_norm)

    # Step 6 — Rolling correlation C(t)
    corr = rolling_correlation(X, EUV, _L)

    # Step 7 — ΔΦ(t): use var_b as S, var_x as I proxy, corr as C
    delta_phi = compute_delta_phi(var_b, var_x, corr)

    # Step 8 — Normalize ΔΦ
    delta_phi_norm = normalize_01(delta_phi)

    # Step 9 — Classify final regime
    valid_dpn = delta_phi_norm[~np.isnan(delta_phi_norm)]
    if len(valid_dpn) == 0:
        regime = "Isostasis"
    else:
        regime = classify_regime(float(valid_dpn[-1]))

    # Step 10 — χ(t) memory variable
    chi = compute_chi(var_b, _L)

    return {
        "var_x": var_x,
        "var_b": var_b,
        "d_euv": d_euv,
        "var_x_norm": var_x_norm,
        "var_b_norm": var_b_norm,
        "d_euv_norm": d_euv_norm,
        "indicator": indicator,
        "corr": corr,
        "delta_phi": delta_phi,
        "delta_phi_norm": delta_phi_norm,
        "regime": regime,
        "chi": chi,
    }


# ---------------------------------------------------------------------------
# Tests — output lengths
# ---------------------------------------------------------------------------


class TestOutputLengths:
    """All pipeline outputs must have the same length as the input."""

    def test_var_x_length(self, pipeline_outputs):
        assert len(pipeline_outputs["var_x"]) == _N

    def test_var_b_length(self, pipeline_outputs):
        assert len(pipeline_outputs["var_b"]) == _N

    def test_d_euv_length(self, pipeline_outputs):
        assert len(pipeline_outputs["d_euv"]) == _N

    def test_indicator_length(self, pipeline_outputs):
        assert len(pipeline_outputs["indicator"]) == _N

    def test_corr_length(self, pipeline_outputs):
        assert len(pipeline_outputs["corr"]) == _N

    def test_delta_phi_length(self, pipeline_outputs):
        assert len(pipeline_outputs["delta_phi"]) == _N

    def test_delta_phi_norm_length(self, pipeline_outputs):
        assert len(pipeline_outputs["delta_phi_norm"]) == _N

    def test_chi_length(self, pipeline_outputs):
        assert len(pipeline_outputs["chi"]) == _N


# ---------------------------------------------------------------------------
# Tests — NaN budget
# ---------------------------------------------------------------------------


class TestNanBudget:
    """NaN values must be confined to the expected warm-up window."""

    def test_var_x_nans_only_in_warmup(self, pipeline_outputs):
        """Var_L[X] NaNs must be limited to the first L-1 positions."""
        var_x = pipeline_outputs["var_x"]
        assert np.all(np.isnan(var_x[: _L - 1]))
        assert np.all(~np.isnan(var_x[_L - 1 :]))

    def test_var_b_nans_only_in_warmup(self, pipeline_outputs):
        var_b = pipeline_outputs["var_b"]
        assert np.all(np.isnan(var_b[: _L - 1]))
        assert np.all(~np.isnan(var_b[_L - 1 :]))

    def test_corr_nans_only_in_warmup(self, pipeline_outputs):
        corr = pipeline_outputs["corr"]
        assert np.all(np.isnan(corr[: _L - 1]))
        assert np.all(~np.isnan(corr[_L - 1 :]))

    def test_chi_nans_only_in_warmup(self, pipeline_outputs):
        chi = pipeline_outputs["chi"]
        assert np.all(np.isnan(chi[: _L - 1]))
        assert np.all(~np.isnan(chi[_L - 1 :]))

    def test_d_euv_no_nans(self, pipeline_outputs):
        """euv_derivative (np.gradient) must produce no NaNs."""
        assert not np.any(np.isnan(pipeline_outputs["d_euv"]))

    def test_delta_phi_norm_no_nans_after_warmup(self, pipeline_outputs):
        """ΔΦ_norm should have no NaN values beyond the warm-up region."""
        dpn = pipeline_outputs["delta_phi_norm"]
        # The warm-up region for ΔΦ spans at least _L positions (from rolling
        # ops) plus 1 extra from the diff; allow up to _L positions.
        valid_region = dpn[_L:]
        assert np.all(~np.isnan(valid_region)), (
            f"Unexpected NaN values found in ΔΦ_norm after warm-up: "
            f"{np.sum(np.isnan(valid_region))} NaNs"
        )


# ---------------------------------------------------------------------------
# Tests — value ranges
# ---------------------------------------------------------------------------


class TestValueRanges:
    """Normalized outputs must be in [0, 1]; I(t) must be in [0, 1]."""

    def test_delta_phi_norm_in_unit_interval(self, pipeline_outputs):
        """All non-NaN ΔΦ_norm values must be in [0, 1]."""
        dpn = pipeline_outputs["delta_phi_norm"]
        valid = dpn[~np.isnan(dpn)]
        assert np.all(valid >= 0.0) and np.all(valid <= 1.0)

    def test_indicator_in_unit_interval(self, pipeline_outputs):
        """All non-NaN I(t) values must be in [0, 1]."""
        ind = pipeline_outputs["indicator"]
        valid = ind[~np.isnan(ind)]
        assert np.all(valid >= 0.0) and np.all(valid <= 1.0)

    def test_var_x_norm_in_unit_interval(self, pipeline_outputs):
        vxn = pipeline_outputs["var_x_norm"]
        valid = vxn[~np.isnan(vxn)]
        assert np.all(valid >= 0.0) and np.all(valid <= 1.0)

    def test_var_b_norm_in_unit_interval(self, pipeline_outputs):
        vbn = pipeline_outputs["var_b_norm"]
        valid = vbn[~np.isnan(vbn)]
        assert np.all(valid >= 0.0) and np.all(valid <= 1.0)


# ---------------------------------------------------------------------------
# Tests — regime classification
# ---------------------------------------------------------------------------


class TestRegimeClassification:
    """The regime label must be one of the four valid strings from REGIME_LABELS."""

    def test_regime_is_valid_string(self, pipeline_outputs):
        assert isinstance(pipeline_outputs["regime"], str)

    def test_regime_in_regime_labels(self, pipeline_outputs):
        assert pipeline_outputs["regime"] in REGIME_LABELS, (
            f"Unexpected regime label: {pipeline_outputs['regime']!r}"
        )


# ---------------------------------------------------------------------------
# Tests — χ(t) monotonicity
# ---------------------------------------------------------------------------


class TestChiMonotonicity:
    """χ(t) must be monotonically non-decreasing after the warm-up window."""

    def test_chi_non_decreasing_after_warmup(self, pipeline_outputs):
        chi = pipeline_outputs["chi"]
        valid = chi[_L - 1 :]
        diffs = np.diff(valid)
        assert np.all(diffs >= -1e-12), (
            f"χ(t) is not monotonically non-decreasing after warm-up; "
            f"min diff = {diffs.min():.6e}"
        )


# ---------------------------------------------------------------------------
# Smoke tests — new plot functions
# ---------------------------------------------------------------------------


class TestPlotFunctionSmoke:
    """Smoke tests: new plot functions must return (fig, ax) without error."""

    def test_plot_delta_phi_returns_fig_ax(self, synthetic_times, pipeline_outputs):
        dpn = pipeline_outputs["delta_phi_norm"]
        fig, ax = plot_delta_phi(synthetic_times, dpn)
        assert isinstance(fig, plt.Figure)
        assert hasattr(ax, "plot")
        plt.close(fig)

    def test_plot_delta_phi_uses_provided_ax(self, synthetic_times, pipeline_outputs):
        dpn = pipeline_outputs["delta_phi_norm"]
        fig_in, ax_in = plt.subplots()
        fig_out, ax_out = plot_delta_phi(synthetic_times, dpn, ax=ax_in)
        assert fig_out is fig_in
        assert ax_out is ax_in
        plt.close(fig_in)

    def test_plot_psi_trajectory_returns_fig_ax(self, pipeline_outputs):
        phi = pipeline_outputs["var_x_norm"]
        chi = pipeline_outputs["chi"]
        fig, ax = plot_psi_trajectory(phi, chi)
        assert isinstance(fig, plt.Figure)
        assert hasattr(ax, "plot")
        plt.close(fig)

    def test_plot_psi_trajectory_with_times(self, synthetic_times, pipeline_outputs):
        phi = pipeline_outputs["var_x_norm"]
        chi = pipeline_outputs["chi"]
        fig, ax = plot_psi_trajectory(phi, chi, times=synthetic_times)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_plot_psi_trajectory_uses_provided_ax(self, pipeline_outputs):
        phi = pipeline_outputs["var_x_norm"]
        chi = pipeline_outputs["chi"]
        fig_in, ax_in = plt.subplots()
        fig_out, ax_out = plot_psi_trajectory(phi, chi, ax=ax_in)
        assert fig_out is fig_in
        assert ax_out is ax_in
        plt.close(fig_in)

    def test_plot_composite_indicator_returns_fig_ax(
        self, synthetic_times, pipeline_outputs
    ):
        ind = pipeline_outputs["indicator"]
        fig, ax = plot_composite_indicator(synthetic_times, ind)
        assert isinstance(fig, plt.Figure)
        assert hasattr(ax, "plot")
        plt.close(fig)

    def test_plot_composite_indicator_uses_provided_ax(
        self, synthetic_times, pipeline_outputs
    ):
        ind = pipeline_outputs["indicator"]
        fig_in, ax_in = plt.subplots()
        fig_out, ax_out = plot_composite_indicator(synthetic_times, ind, ax=ax_in)
        assert fig_out is fig_in
        assert ax_out is ax_in
        plt.close(fig_in)

    def test_plot_composite_indicator_no_exception_with_kwargs(
        self, synthetic_times, pipeline_outputs
    ):
        ind = pipeline_outputs["indicator"]
        fig, ax = plot_composite_indicator(synthetic_times, ind, color="red")
        plt.close(fig)
