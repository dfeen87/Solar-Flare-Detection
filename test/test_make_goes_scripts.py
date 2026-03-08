"""
test_make_goes_scripts.py — Tests for make_goes_figures.py and
make_goes_summary_report.py.

All tests use synthetic in-memory data so no network connection or local data
cache is required.  Both scripts' public functions are tested via import with
their data-loading helpers patched out using ``unittest.mock``.

Figures produced
----------------
  fig6_goes_xray_flux.png
  fig7_windowed_variance.png
  fig8_flare_event_overlay.png

CSV tables produced
-------------------
  goes_table_a_flux.csv          — columns: time_utc | xray_flux
  goes_table_b_rolling_variance.csv — columns: time_utc | rolling_variance | window_L
  goes_table_c_flare_overlay.csv — columns: time_utc | xray_flux | flare_flag | flare_class

PDF report
----------
  goes_summary_report.pdf
"""

import os
import sys
import importlib
import tempfile
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import numpy as np
import matplotlib
matplotlib.use("Agg")
import pytest
import pandas as pd

# ---------------------------------------------------------------------------
# Ensure both the repo root and the script directory are importable.
# (conftest.py already adds the repo root; the scripts themselves handle
# their own sys.path insertion when run as __main__, but here we import
# them as modules so we replicate the same path setup.)
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)
_SCRIPT_DIR = os.path.join(
    _REPO_ROOT, "domains", "spiral_time", "examples_python"
)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

import make_goes_figures as mgf        # noqa: E402
import make_goes_summary_report as mgsr  # noqa: E402
import make_fig6_goes_flux as mf6        # noqa: E402

# ---------------------------------------------------------------------------
# Synthetic data helpers
# ---------------------------------------------------------------------------

_N = 300          # number of flux samples
_WINDOW_L = 200   # must match the scripts' WINDOW_L constant
_BUMP_CENTER = 0.6   # fractional position of the synthetic flare bump along [0, 1]
_BUMP_WIDTH = 0.01   # Gaussian σ of the synthetic flare bump


def _make_times(n=_N):
    """Return a list of *n* consecutive UTC datetimes at 1-minute spacing."""
    t0 = datetime(2024, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
    return [t0 + timedelta(minutes=i) for i in range(n)]


def _make_flux(n=_N, seed=42):
    """Return a synthetic positive X-ray flux array of length *n*."""
    rng = np.random.default_rng(seed)
    base = np.full(n, 1e-7)
    bump = 5e-7 * np.exp(-((np.linspace(0, 1, n) - _BUMP_CENTER) ** 2) / (2 * _BUMP_WIDTH ** 2))
    noise = rng.standard_normal(n) * 5e-9
    return np.abs(base + bump + noise)


def _make_flare_df(times):
    """Return a minimal NOAA flare DataFrame with two events."""
    onset1 = times[50]
    onset2 = times[150]
    return pd.DataFrame({
        "time_begin": [onset1, onset2],
        "time_max": [onset1 + timedelta(minutes=5), onset2 + timedelta(minutes=5)],
        "time_end": [onset1 + timedelta(minutes=20), onset2 + timedelta(minutes=20)],
        "class_type": ["M", "X"],
        "class_num": [2.3, 1.0],
    })


def _make_flux_df(times):
    """Return a minimal GOES flux DataFrame."""
    return pd.DataFrame({"time": times, "flux": _make_flux()})


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def syn_times():
    return _make_times()


@pytest.fixture(scope="module")
def syn_flux(syn_times):
    return _make_flux()


@pytest.fixture(scope="module")
def syn_flare_data(syn_times):
    """Return (onset_time, flare_class) tuples consistent with _make_flare_df."""
    return [
        (syn_times[50], "M2.3"),
        (syn_times[150], "X1"),
    ]


# ===========================================================================
# Tests for make_goes_figures.py
# ===========================================================================


class TestMakeGoesFigures:
    """Test the three figure-producing functions in make_goes_figures.py."""

    def test_make_fig6_creates_png(self, syn_times, syn_flux, tmp_path):
        """make_fig6 must create a non-empty PNG file."""
        original_dir = mgf._OUTPUT_DIR
        mgf._OUTPUT_DIR = str(tmp_path)
        try:
            path = mgf.make_fig6(syn_times, syn_flux)
        finally:
            mgf._OUTPUT_DIR = original_dir

        assert os.path.isfile(path), "fig6 PNG not created"
        assert os.path.getsize(path) > 0, "fig6 PNG is empty"
        assert path.endswith("fig6_goes_xray_flux.png")

    def test_make_fig7_creates_png(self, syn_times, syn_flux, tmp_path):
        """make_fig7 must create a non-empty PNG file."""
        from shared.math_utils import rolling_variance
        var = rolling_variance(syn_flux, _WINDOW_L)

        original_dir = mgf._OUTPUT_DIR
        mgf._OUTPUT_DIR = str(tmp_path)
        try:
            path = mgf.make_fig7(syn_times, syn_flux)
        finally:
            mgf._OUTPUT_DIR = original_dir

        assert os.path.isfile(path), "fig7 PNG not created"
        assert os.path.getsize(path) > 0, "fig7 PNG is empty"
        assert path.endswith("fig7_windowed_variance.png")

    def test_make_fig8_creates_png(self, syn_times, syn_flux, syn_flare_data,
                                   tmp_path):
        """make_fig8 must create a non-empty PNG file."""
        flare_times = [t for t, _ in syn_flare_data]

        original_dir = mgf._OUTPUT_DIR
        mgf._OUTPUT_DIR = str(tmp_path)
        try:
            path = mgf.make_fig8(syn_times, syn_flux, flare_times)
        finally:
            mgf._OUTPUT_DIR = original_dir

        assert os.path.isfile(path), "fig8 PNG not created"
        assert os.path.getsize(path) > 0, "fig8 PNG is empty"
        assert path.endswith("fig8_flare_event_overlay.png")

    def test_make_fig8_no_flares_no_error(self, syn_times, syn_flux, tmp_path):
        """make_fig8 must succeed gracefully when the flare list is empty."""
        original_dir = mgf._OUTPUT_DIR
        mgf._OUTPUT_DIR = str(tmp_path)
        try:
            path = mgf.make_fig8(syn_times, syn_flux, [])
        finally:
            mgf._OUTPUT_DIR = original_dir

        assert os.path.isfile(path)

    def test_load_flare_times_uses_time_begin(self, syn_times):
        """_load_flare_times prefers time_begin over time_max."""
        flux_df = _make_flux_df(syn_times)
        flare_df = _make_flare_df(syn_times)

        with patch("make_goes_figures.load_xray_flux", return_value=flux_df), \
             patch("make_goes_figures.load_xray_flares", return_value=flare_df):
            times_loaded, _ = mgf._load_flux()
            flare_times = mgf._load_flare_times()

        assert len(flare_times) == 2
        assert flare_times[0] == syn_times[50]
        assert flare_times[1] == syn_times[150]


# ===========================================================================
# Tests for make_goes_summary_report.py
# ===========================================================================


class TestBuildTableA:
    """Table A must contain time_utc and xray_flux columns."""

    def test_column_names(self, syn_times, syn_flux):
        df = mgsr.build_table_a(syn_times, syn_flux)
        assert list(df.columns) == ["time_utc", "xray_flux"]

    def test_row_count_matches_input(self, syn_times, syn_flux):
        df = mgsr.build_table_a(syn_times, syn_flux)
        assert len(df) == len(syn_times)

    def test_time_utc_is_iso8601(self, syn_times, syn_flux):
        df = mgsr.build_table_a(syn_times, syn_flux)
        # First entry should look like "2024-01-15T00:00:00Z"
        assert df["time_utc"].iloc[0].endswith("Z")
        assert "T" in df["time_utc"].iloc[0]

    def test_xray_flux_values_preserved(self, syn_times, syn_flux):
        df = mgsr.build_table_a(syn_times, syn_flux)
        np.testing.assert_array_almost_equal(df["xray_flux"].to_numpy(), syn_flux)


class TestBuildTableB:
    """Table B must contain time_utc, rolling_variance, and window_L columns."""

    def test_column_names(self, syn_times, syn_flux):
        from shared.math_utils import rolling_variance
        var = rolling_variance(syn_flux, _WINDOW_L)
        df = mgsr.build_table_b(syn_times, var)
        assert list(df.columns) == ["time_utc", "rolling_variance", "window_L"]

    def test_row_count_matches_input(self, syn_times, syn_flux):
        from shared.math_utils import rolling_variance
        var = rolling_variance(syn_flux, _WINDOW_L)
        df = mgsr.build_table_b(syn_times, var)
        assert len(df) == len(syn_times)

    def test_window_l_column_constant(self, syn_times, syn_flux):
        from shared.math_utils import rolling_variance
        var = rolling_variance(syn_flux, _WINDOW_L)
        df = mgsr.build_table_b(syn_times, var)
        assert (df["window_L"] == _WINDOW_L).all()

    def test_first_entries_are_nan(self, syn_times, syn_flux):
        """First WINDOW_L-1 rolling_variance entries must be NaN (warm-up)."""
        from shared.math_utils import rolling_variance
        var = rolling_variance(syn_flux, _WINDOW_L)
        df = mgsr.build_table_b(syn_times, var)
        nan_count = df["rolling_variance"].isna().sum()
        assert nan_count == _WINDOW_L - 1, (
            f"Expected {_WINDOW_L - 1} NaN rows, got {nan_count}"
        )


class TestBuildTableC:
    """Table C must contain time_utc, xray_flux, flare_flag, flare_class."""

    def test_column_names(self, syn_times, syn_flux, syn_flare_data):
        df = mgsr.build_table_c(syn_times, syn_flux, syn_flare_data)
        assert list(df.columns) == [
            "time_utc", "xray_flux", "flare_flag", "flare_class"
        ]

    def test_row_count_matches_input(self, syn_times, syn_flux, syn_flare_data):
        df = mgsr.build_table_c(syn_times, syn_flux, syn_flare_data)
        assert len(df) == len(syn_times)

    def test_flare_flags_at_onset_times(self, syn_times, syn_flux, syn_flare_data):
        """Rows at flare onset times must have flare_flag == 1."""
        df = mgsr.build_table_c(syn_times, syn_flux, syn_flare_data)
        # Onset indices are 50 and 150
        assert df["flare_flag"].iloc[50] == 1
        assert df["flare_flag"].iloc[150] == 1

    def test_flare_class_at_onset_times(self, syn_times, syn_flux, syn_flare_data):
        """Rows at flare onset times must have the correct NOAA class string."""
        df = mgsr.build_table_c(syn_times, syn_flux, syn_flare_data)
        assert df["flare_class"].iloc[50] == "M2.3"
        assert df["flare_class"].iloc[150] == "X1"

    def test_non_flare_rows_have_zero_flag(self, syn_times, syn_flux,
                                            syn_flare_data):
        """Rows without a flare onset must have flare_flag == 0."""
        df = mgsr.build_table_c(syn_times, syn_flux, syn_flare_data)
        non_flare = df[(df["flare_flag"] == 0)]
        assert len(non_flare) == _N - 2

    def test_empty_flare_data_all_zeros(self, syn_times, syn_flux):
        """When flare_data is empty every flare_flag must be 0."""
        df = mgsr.build_table_c(syn_times, syn_flux, [])
        assert (df["flare_flag"] == 0).all()
        assert (df["flare_class"] == "").all()


class TestMakePdfReport:
    """PDF report must be created as a valid (non-empty) PDF file."""

    def test_pdf_created(self, syn_times, syn_flux, syn_flare_data, tmp_path):
        from shared.math_utils import rolling_variance

        var = rolling_variance(syn_flux, _WINDOW_L)
        table_a = mgsr.build_table_a(syn_times, syn_flux)
        table_b = mgsr.build_table_b(syn_times, var)
        table_c = mgsr.build_table_c(syn_times, syn_flux, syn_flare_data)

        # Generate the three figures first (they are embedded in the PDF).
        original_dir = mgsr._OUTPUT_DIR
        mgsr._OUTPUT_DIR = str(tmp_path)
        try:
            p6 = mgsr.make_fig6(syn_times, syn_flux)
            p7 = mgsr.make_fig7(syn_times, var)
            p8 = mgsr.make_fig8(syn_times, syn_flux, syn_flare_data)
            pdf_path = mgsr.make_pdf_report(
                syn_times, p6, p7, p8, table_a, table_b, table_c
            )
        finally:
            mgsr._OUTPUT_DIR = original_dir

        assert os.path.isfile(pdf_path), "PDF report not created"
        assert os.path.getsize(pdf_path) > 0, "PDF report is empty"
        assert pdf_path.endswith("goes_summary_report.pdf")

    def test_pdf_starts_with_pdf_magic_bytes(self, syn_times, syn_flux,
                                              syn_flare_data, tmp_path):
        """The generated file must be a valid PDF (begins with %PDF)."""
        from shared.math_utils import rolling_variance

        var = rolling_variance(syn_flux, _WINDOW_L)
        table_a = mgsr.build_table_a(syn_times, syn_flux)
        table_b = mgsr.build_table_b(syn_times, var)
        table_c = mgsr.build_table_c(syn_times, syn_flux, syn_flare_data)

        original_dir = mgsr._OUTPUT_DIR
        mgsr._OUTPUT_DIR = str(tmp_path)
        try:
            p6 = mgsr.make_fig6(syn_times, syn_flux)
            p7 = mgsr.make_fig7(syn_times, var)
            p8 = mgsr.make_fig8(syn_times, syn_flux, syn_flare_data)
            pdf_path = mgsr.make_pdf_report(
                syn_times, p6, p7, p8, table_a, table_b, table_c
            )
        finally:
            mgsr._OUTPUT_DIR = original_dir

        with open(pdf_path, "rb") as fh:
            header = fh.read(4)
        assert header == b"%PDF", f"File does not start with PDF magic bytes: {header!r}"


class TestMakeSummaryReportFigures:
    """Figure-producing functions in make_goes_summary_report.py."""

    def test_make_fig6_creates_png(self, syn_times, syn_flux, tmp_path):
        original_dir = mgsr._OUTPUT_DIR
        mgsr._OUTPUT_DIR = str(tmp_path)
        try:
            path = mgsr.make_fig6(syn_times, syn_flux)
        finally:
            mgsr._OUTPUT_DIR = original_dir
        assert os.path.isfile(path)
        assert path.endswith("fig6_goes_xray_flux.png")

    def test_make_fig7_creates_png(self, syn_times, syn_flux, tmp_path):
        from shared.math_utils import rolling_variance
        var = rolling_variance(syn_flux, _WINDOW_L)

        original_dir = mgsr._OUTPUT_DIR
        mgsr._OUTPUT_DIR = str(tmp_path)
        try:
            path = mgsr.make_fig7(syn_times, var)
        finally:
            mgsr._OUTPUT_DIR = original_dir
        assert os.path.isfile(path)
        assert path.endswith("fig7_windowed_variance.png")

    def test_make_fig8_creates_png(self, syn_times, syn_flux, syn_flare_data,
                                   tmp_path):
        original_dir = mgsr._OUTPUT_DIR
        mgsr._OUTPUT_DIR = str(tmp_path)
        try:
            path = mgsr.make_fig8(syn_times, syn_flux, syn_flare_data)
        finally:
            mgsr._OUTPUT_DIR = original_dir
        assert os.path.isfile(path)
        assert path.endswith("fig8_flare_event_overlay.png")


class TestLoadFlares:
    """_load_flares must parse the NOAA flare catalogue correctly."""

    def test_returns_onset_class_tuples(self, syn_times):
        flux_df = _make_flux_df(syn_times)
        flare_df = _make_flare_df(syn_times)

        with patch("make_goes_summary_report.load_xray_flux", return_value=flux_df), \
             patch("make_goes_summary_report.load_xray_flares",
                   return_value=flare_df):
            flare_data = mgsr._load_flares()

        assert len(flare_data) == 2
        for onset, cls in flare_data:
            assert isinstance(onset, datetime)
            assert isinstance(cls, str)

    def test_flare_class_format(self, syn_times):
        """Flare class should combine class_type and class_num (e.g. 'M2.3').

        The catalogue is iterated in row order; onset at index 50 is M2.3 and
        onset at index 150 is X1.
        """
        flux_df = _make_flux_df(syn_times)
        flare_df = _make_flare_df(syn_times)

        with patch("make_goes_summary_report.load_xray_flux", return_value=flux_df), \
             patch("make_goes_summary_report.load_xray_flares",
                   return_value=flare_df):
            flare_data = mgsr._load_flares()

        assert len(flare_data) == 2
        assert flare_data[0][0] == syn_times[50],  "first onset must be at index 50"
        assert flare_data[0][1] == "M2.3",          "first class must be M2.3"
        assert flare_data[1][0] == syn_times[150], "second onset must be at index 150"
        assert flare_data[1][1] == "X1",            "second class must be X1"


# ===========================================================================
# Tests for make_fig6_goes_flux.py
# ===========================================================================


class TestMakeFig6GoesFlux:
    """Tests for the standalone make_fig6_goes_flux.py script."""

    def test_make_fig6_creates_png(self, syn_times, syn_flux, tmp_path):
        """make_fig6 must create a non-empty PNG file."""
        original_dir = mf6._OUTPUT_DIR
        mf6._OUTPUT_DIR = str(tmp_path)
        try:
            path = mf6.make_fig6(syn_times, syn_flux)
        finally:
            mf6._OUTPUT_DIR = original_dir

        assert os.path.isfile(path), "fig6 PNG not created"
        assert os.path.getsize(path) > 0, "fig6 PNG is empty"
        assert path.endswith("fig6_goes_xray_flux.png")

    def test_make_fig6_returns_absolute_path(self, syn_times, syn_flux, tmp_path):
        """make_fig6 must return an absolute path."""
        original_dir = mf6._OUTPUT_DIR
        mf6._OUTPUT_DIR = str(tmp_path)
        try:
            path = mf6.make_fig6(syn_times, syn_flux)
        finally:
            mf6._OUTPUT_DIR = original_dir

        assert os.path.isabs(path), "returned path must be absolute"

    def test_make_fig7_creates_png(self, syn_times, syn_flux, tmp_path):
        """make_fig7 must create a non-empty PNG file."""
        original_dir = mf6._OUTPUT_DIR
        mf6._OUTPUT_DIR = str(tmp_path)
        try:
            path = mf6.make_fig7(syn_times, syn_flux)
        finally:
            mf6._OUTPUT_DIR = original_dir

        assert os.path.isfile(path), "fig7 PNG not created"
        assert os.path.getsize(path) > 0, "fig7 PNG is empty"
        assert path.endswith("fig7_windowed_variance.png")

    def test_make_fig7_returns_absolute_path(self, syn_times, syn_flux, tmp_path):
        """make_fig7 must return an absolute path."""
        original_dir = mf6._OUTPUT_DIR
        mf6._OUTPUT_DIR = str(tmp_path)
        try:
            path = mf6.make_fig7(syn_times, syn_flux)
        finally:
            mf6._OUTPUT_DIR = original_dir

        assert os.path.isabs(path), "returned path must be absolute"

    def test_make_fig8_creates_png(self, syn_times, syn_flux, syn_flare_data,
                                   tmp_path):
        """make_fig8 must create a non-empty PNG file."""
        flare_times = [t for t, _ in syn_flare_data]

        original_dir = mf6._OUTPUT_DIR
        mf6._OUTPUT_DIR = str(tmp_path)
        try:
            path = mf6.make_fig8(syn_times, syn_flux, flare_times)
        finally:
            mf6._OUTPUT_DIR = original_dir

        assert os.path.isfile(path), "fig8 PNG not created"
        assert os.path.getsize(path) > 0, "fig8 PNG is empty"
        assert path.endswith("fig8_flare_event_overlay.png")

    def test_make_fig8_no_flares_no_error(self, syn_times, syn_flux, tmp_path):
        """make_fig8 must succeed gracefully when the flare list is empty."""
        original_dir = mf6._OUTPUT_DIR
        mf6._OUTPUT_DIR = str(tmp_path)
        try:
            path = mf6.make_fig8(syn_times, syn_flux, [])
        finally:
            mf6._OUTPUT_DIR = original_dir

        assert os.path.isfile(path)

    def test_make_fig8_returns_absolute_path(self, syn_times, syn_flux,
                                             syn_flare_data, tmp_path):
        """make_fig8 must return an absolute path."""
        flare_times = [t for t, _ in syn_flare_data]

        original_dir = mf6._OUTPUT_DIR
        mf6._OUTPUT_DIR = str(tmp_path)
        try:
            path = mf6.make_fig8(syn_times, syn_flux, flare_times)
        finally:
            mf6._OUTPUT_DIR = original_dir

        assert os.path.isabs(path), "returned path must be absolute"
