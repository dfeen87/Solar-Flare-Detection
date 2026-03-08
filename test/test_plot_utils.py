"""
test_plot_utils.py — Smoke tests for shared/plot_utils.py.

Verifies that each plotting function:
  - Executes without raising an exception.
  - Returns the expected (fig, ax) types.
  - Produces a matplotlib Figure and Axes object.

No display is required; matplotlib is configured to use the non-interactive
"Agg" backend so the tests run in headless environments.
"""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pytest

from shared.plot_utils import (
    FLARE_CLASS_COLORS,
    style_solar_axes,
    plot_xray_flux,
    plot_rolling_variance,
    plot_flare_overlay,
    add_regime_bands,
)
from shared.math_utils import rolling_variance

# ---------------------------------------------------------------------------
# Module-level constants used in fixtures / tests
# ---------------------------------------------------------------------------

#: Window length used for rolling-variance fixtures and tests.
_VARIANCE_WINDOW_L: int = 5

#: Typical X-ray flux scale factor (W m⁻²) for synthetic data.
_FLUX_SCALE: float = 1e-6

#: Typical X-ray flux background offset (W m⁻²) for synthetic data.
_FLUX_OFFSET: float = 1e-7


# ---------------------------------------------------------------------------
# Fixtures — minimal synthetic data sets
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_times():
    return np.linspace(0, 100, 50)


@pytest.fixture()
def sample_flux():
    rng = np.random.default_rng(42)
    return np.abs(rng.standard_normal(50)) * _FLUX_SCALE + _FLUX_OFFSET


@pytest.fixture()
def sample_variance(sample_flux):
    return rolling_variance(sample_flux, L=_VARIANCE_WINDOW_L)


@pytest.fixture()
def sample_flare_times(sample_times):
    return sample_times[[10, 25, 40]]


@pytest.fixture()
def sample_flare_classes():
    return ["X", "M", "C"]


@pytest.fixture()
def sample_delta_phi_norm():
    return np.linspace(0.0, 1.0, 50)


# ===========================================================================
# FLARE_CLASS_COLORS constant
# ===========================================================================


class TestFlareClassColors:
    def test_has_expected_keys(self):
        """FLARE_CLASS_COLORS must contain X, M, C, B, A keys."""
        assert set(FLARE_CLASS_COLORS.keys()) == {"X", "M", "C", "B", "A"}

    def test_values_are_strings(self):
        """All color values must be strings (hex or named colors)."""
        for cls, color in FLARE_CLASS_COLORS.items():
            assert isinstance(color, str), f"Color for class {cls!r} is not a string"

    def test_x_is_red_family(self):
        """Class X uses red color (#e74c3c)."""
        assert FLARE_CLASS_COLORS["X"] == "#e74c3c"

    def test_m_is_orange_family(self):
        """Class M uses orange color (#e67e22)."""
        assert FLARE_CLASS_COLORS["M"] == "#e67e22"


# ===========================================================================
# style_solar_axes
# ===========================================================================


class TestStyleSolarAxes:
    def test_no_error_minimal(self):
        """style_solar_axes runs without error on a bare axes."""
        fig, ax = plt.subplots()
        style_solar_axes(ax)
        plt.close(fig)

    def test_title_applied(self):
        """Provided title appears on the axes."""
        fig, ax = plt.subplots()
        style_solar_axes(ax, title="Test Title")
        assert ax.get_title() == "Test Title"
        plt.close(fig)

    def test_ylabel_applied(self):
        """Provided ylabel appears on the axes."""
        fig, ax = plt.subplots()
        style_solar_axes(ax, ylabel="Y Label")
        assert ax.get_ylabel() == "Y Label"
        plt.close(fig)

    def test_grid_enabled(self):
        """Grid should be enabled after styling."""
        fig, ax = plt.subplots()
        style_solar_axes(ax)
        assert ax.get_xgridlines() or ax.xaxis.get_gridlines()
        plt.close(fig)


# ===========================================================================
# plot_xray_flux
# ===========================================================================


class TestPlotXrayFlux:
    def test_returns_fig_and_ax(self, sample_times, sample_flux):
        """Returns (fig, ax) tuple with correct types."""
        fig, ax = plot_xray_flux(sample_times, sample_flux)
        assert isinstance(fig, plt.Figure)
        assert hasattr(ax, "semilogy")
        plt.close(fig)

    def test_uses_provided_ax(self, sample_times, sample_flux):
        """When ax is provided, uses it and returns the same figure."""
        fig_in, ax_in = plt.subplots()
        fig_out, ax_out = plot_xray_flux(sample_times, sample_flux, ax=ax_in)
        assert fig_out is fig_in
        assert ax_out is ax_in
        plt.close(fig_in)

    def test_ylabel_set(self, sample_times, sample_flux):
        """Y-axis label should be set to flux units."""
        _, ax = plot_xray_flux(sample_times, sample_flux)
        assert "W" in ax.get_ylabel() or "Flux" in ax.get_ylabel()
        plt.close()

    def test_no_exception_with_kwargs(self, sample_times, sample_flux):
        """Extra kwargs (e.g., color) are forwarded without error."""
        fig, ax = plot_xray_flux(sample_times, sample_flux, color="green")
        plt.close(fig)


# ===========================================================================
# plot_rolling_variance
# ===========================================================================


class TestPlotRollingVariance:
    def test_returns_fig_and_ax(self, sample_times, sample_variance):
        """Returns (fig, ax) tuple with correct types."""
        fig, ax = plot_rolling_variance(sample_times, sample_variance, L=_VARIANCE_WINDOW_L)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_uses_provided_ax(self, sample_times, sample_variance):
        """When ax is provided, uses it and returns the same figure."""
        fig_in, ax_in = plt.subplots()
        fig_out, ax_out = plot_rolling_variance(
            sample_times, sample_variance, L=_VARIANCE_WINDOW_L, ax=ax_in
        )
        assert fig_out is fig_in
        assert ax_out is ax_in
        plt.close(fig_in)

    def test_label_contains_L(self, sample_times, sample_variance):
        """The plotted line label should reference the window length L."""
        _, ax = plot_rolling_variance(sample_times, sample_variance, L=_VARIANCE_WINDOW_L)
        lines = ax.get_lines()
        assert any(str(_VARIANCE_WINDOW_L) in (ln.get_label() or "") for ln in lines)
        plt.close()


# ===========================================================================
# plot_flare_overlay
# ===========================================================================


class TestPlotFlareOverlay:
    def test_returns_fig_and_ax(
        self, sample_times, sample_flux, sample_flare_times, sample_flare_classes
    ):
        """Returns (fig, ax) tuple with correct types."""
        fig, ax = plot_flare_overlay(
            sample_times, sample_flux, sample_flare_times, sample_flare_classes
        )
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_uses_provided_ax(
        self, sample_times, sample_flux, sample_flare_times, sample_flare_classes
    ):
        """When ax is provided, uses it and returns the same figure."""
        fig_in, ax_in = plt.subplots()
        fig_out, ax_out = plot_flare_overlay(
            sample_times, sample_flux, sample_flare_times, sample_flare_classes, ax=ax_in
        )
        assert fig_out is fig_in
        assert ax_out is ax_in
        plt.close(fig_in)

    def test_empty_flare_list_no_error(self, sample_times, sample_flux):
        """Empty flare list should not raise."""
        fig, ax = plot_flare_overlay(sample_times, sample_flux, [], [])
        plt.close(fig)

    def test_unknown_class_falls_back(self, sample_times, sample_flux):
        """Unknown flare class letter should use fallback color without error."""
        fig, ax = plot_flare_overlay(
            sample_times, sample_flux, sample_times[:1], ["Z"]
        )
        plt.close(fig)


# ===========================================================================
# add_regime_bands
# ===========================================================================


class TestAddRegimeBands:
    def test_no_error(self, sample_times, sample_delta_phi_norm):
        """add_regime_bands executes without error."""
        fig, ax = plt.subplots()
        add_regime_bands(ax, sample_delta_phi_norm, sample_times)
        plt.close(fig)

    def test_adds_patches(self, sample_times, sample_delta_phi_norm):
        """Calling add_regime_bands should add horizontal span patches to ax."""
        fig, ax = plt.subplots()
        patches_before = len(ax.patches)
        add_regime_bands(ax, sample_delta_phi_norm, sample_times)
        patches_after = len(ax.patches)
        assert patches_after > patches_before
        plt.close(fig)

    def test_four_bands_added(self, sample_times, sample_delta_phi_norm):
        """Exactly four regime bands (one per regime) should be added."""
        fig, ax = plt.subplots()
        add_regime_bands(ax, sample_delta_phi_norm, sample_times)
        # Each axhspan creates one Polygon patch
        assert len(ax.patches) == 4
        plt.close(fig)
