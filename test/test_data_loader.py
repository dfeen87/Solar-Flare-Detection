"""
test_data_loader.py — Structural smoke tests for shared/data_loader.py.

Verifies that each loader returns a DataFrame with the expected columns.
Tests are skipped gracefully when the local JSON cache files are absent and
the NOAA API is unreachable (e.g. in CI without network access).
"""

import pytest
import pandas as pd

# ---------------------------------------------------------------------------
# Helper — attempt import once; skip entire module if network required but
# the loader itself fails to import for an unrelated reason.
# ---------------------------------------------------------------------------

from shared import data_loader  # noqa: E402


def _try_load(loader_fn):
    """Call *loader_fn* and return the DataFrame, or skip if data unavailable."""
    try:
        return loader_fn()
    except RuntimeError as exc:
        pytest.skip(f"Data not available: {exc}")


# ===========================================================================
# load_xray_flux
# ===========================================================================


class TestLoadXrayFlux:
    def test_returns_dataframe(self):
        df = _try_load(data_loader.load_xray_flux)
        assert isinstance(df, pd.DataFrame)

    def test_has_required_columns(self):
        df = _try_load(data_loader.load_xray_flux)
        assert "time" in df.columns
        assert "flux" in df.columns

    def test_no_extra_unexpected_columns(self):
        df = _try_load(data_loader.load_xray_flux)
        assert set(df.columns) == {"time", "flux"}


# ===========================================================================
# load_xray_flares
# ===========================================================================


class TestLoadXrayFlares:
    def test_returns_dataframe(self):
        df = _try_load(data_loader.load_xray_flares)
        assert isinstance(df, pd.DataFrame)

    def test_has_required_columns(self):
        df = _try_load(data_loader.load_xray_flares)
        required = {"time_begin", "time_max", "time_end", "class_type", "class_num"}
        assert required.issubset(set(df.columns))


# ===========================================================================
# load_magnetometer
# ===========================================================================


class TestLoadMagnetometer:
    def test_returns_dataframe(self):
        df = _try_load(data_loader.load_magnetometer)
        assert isinstance(df, pd.DataFrame)

    def test_has_required_columns(self):
        df = _try_load(data_loader.load_magnetometer)
        assert "time" in df.columns
        assert "He" in df.columns

    def test_no_extra_unexpected_columns(self):
        df = _try_load(data_loader.load_magnetometer)
        assert set(df.columns) == {"time", "He"}


# ===========================================================================
# load_euvs
# ===========================================================================


class TestLoadEuvs:
    def test_returns_dataframe(self):
        df = _try_load(data_loader.load_euvs)
        assert isinstance(df, pd.DataFrame)

    def test_has_time_column(self):
        df = _try_load(data_loader.load_euvs)
        assert "time" in df.columns


# ===========================================================================
# load_xray_background
# ===========================================================================


class TestLoadXrayBackground:
    def test_returns_dataframe(self):
        df = _try_load(data_loader.load_xray_background)
        assert isinstance(df, pd.DataFrame)

    def test_has_required_columns(self):
        df = _try_load(data_loader.load_xray_background)
        assert "time" in df.columns
        assert "background_flux" in df.columns

    def test_no_extra_unexpected_columns(self):
        df = _try_load(data_loader.load_xray_background)
        assert set(df.columns) == {"time", "background_flux"}
