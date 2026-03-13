"""
test_data_loader_long_range.py — Tests for long-range NOAA SWPC ingestion.

All tests monkeypatch the internal fetch function so that no real network
calls are made.  Cache root is redirected to ``tmp_path`` via monkeypatch.
"""

import json
from datetime import datetime, timezone

import pandas as pd
import pytest

from shared import data_loader

# ---------------------------------------------------------------------------
# Fake records for each dataset key
# ---------------------------------------------------------------------------

_FAKE_XRAY = [
    {"time_tag": "2024-01-01T12:00:00Z", "energy": "0.1-0.8nm", "flux": 1.5e-6},
    {"time_tag": "2024-01-02T12:00:00Z", "energy": "0.1-0.8nm", "flux": 2.0e-6},
    {"time_tag": "2024-01-03T00:00:00Z", "energy": "0.1-0.8nm", "flux": 3.0e-6},
]

_FAKE_BACKGROUND = [
    {"time_tag": "2024-01-01T12:00:00Z", "flux": 1.0e-7},
    {"time_tag": "2024-01-02T12:00:00Z", "flux": 1.1e-7},
]

_FAKE_EUVS = [
    {"time_tag": "2024-01-01T12:00:00Z", "satellite": 16, "e_low": 0.1, "e_mid": 0.2},
    {"time_tag": "2024-01-02T12:00:00Z", "satellite": 16, "e_low": 0.3, "e_mid": 0.4},
]

_FAKE_MAGNETO = [
    {"time_tag": "2024-01-01T12:00:00Z", "He": 100.5},
    {"time_tag": "2024-01-02T12:00:00Z", "He": 101.2},
]

_FAKE_FLARES = [
    {
        "begin_time": "2024-01-01T12:00:00Z",
        "max_time": "2024-01-01T12:05:00Z",
        "end_time": "2024-01-01T12:10:00Z",
        "class": "C2.3",
    },
    {
        "begin_time": "2024-01-02T06:00:00Z",
        "max_time": "2024-01-02T06:10:00Z",
        "end_time": "2024-01-02T06:20:00Z",
        "class": "M1.5",
    },
]

_FAKE_DATA = {
    "xray_flux": _FAKE_XRAY,
    "xray_background": _FAKE_BACKGROUND,
    "euvs": _FAKE_EUVS,
    "magnetometer": _FAKE_MAGNETO,
    "flare_catalogue": _FAKE_FLARES,
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _redirect_cache(tmp_path, monkeypatch):
    """Point cache root to a temp directory for every test."""
    cache_root = tmp_path / "data" / "raw" / "goes"
    cache_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(data_loader, "_RAW_CACHE_ROOT", cache_root)


class _FetchCounter:
    """Callable that counts invocations and returns fake data."""

    def __init__(self):
        self.count = 0

    def __call__(self, url, timeout_s=30):
        self.count += 1
        # Determine dataset key from URL
        for key, tmpl in data_loader._RANGE_URL_TEMPLATES.items():
            base = tmpl.split("?")[0]
            if base in url:
                return list(_FAKE_DATA.get(key, []))
        # Fallback: return xray data
        return list(_FAKE_XRAY)


@pytest.fixture()
def fake_fetch(monkeypatch):
    """Monkeypatch ``_fetch_swpc_json`` and return the counter object."""
    counter = _FetchCounter()
    monkeypatch.setattr(data_loader, "_fetch_swpc_json", counter)
    return counter


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCacheBehavior:
    def test_cache_miss_writes_file_and_cache_hit_skips_fetch(
        self, tmp_path, fake_fetch
    ):
        df1 = data_loader.load_goes_xray_range("2024-01-01", "2024-01-03")
        assert fake_fetch.count == 1

        df2 = data_loader.load_goes_xray_range("2024-01-01", "2024-01-03")
        assert fake_fetch.count == 1  # cache hit — no additional fetch

        cache_file = (
            tmp_path / "data" / "raw" / "goes" / "xray_flux"
            / "2024-01-01_to_2024-01-03.json"
        )
        assert cache_file.exists()
        with open(cache_file, "r") as fh:
            cached = json.load(fh)
        assert isinstance(cached, list)

    def test_force_refresh_bypasses_cache(self, fake_fetch):
        data_loader.load_goes_xray_range("2024-01-01", "2024-01-03")
        assert fake_fetch.count == 1

        data_loader.load_goes_xray_range(
            "2024-01-01", "2024-01-03", force_refresh=True
        )
        assert fake_fetch.count == 2


class TestXrayRange:
    def test_xray_range_returns_utc_aware_time_and_expected_columns(
        self, fake_fetch
    ):
        df = data_loader.load_goes_xray_range("2024-01-01", "2024-01-03")
        assert set(df.columns) == {"time", "flux"}
        assert len(df) > 0
        assert df["time"].iloc[0].tzinfo is not None
        assert df["time"].iloc[0].tzinfo == timezone.utc


class TestEuvRange:
    def test_euv_range_has_time_and_at_least_one_channel_column(
        self, fake_fetch
    ):
        df = data_loader.load_goes_euv_range("2024-01-01", "2024-01-03")
        assert "time" in df.columns
        assert len(df.columns) >= 2


class TestMagnetometerRange:
    def test_magnetometer_range_has_expected_columns(self, fake_fetch):
        df = data_loader.load_goes_magnetometer_range(
            "2024-01-01", "2024-01-03"
        )
        assert set(df.columns) == {"time", "He"}


class TestFlareCatalogueRange:
    def test_flare_catalogue_range_schema_sanity(self, fake_fetch):
        df = data_loader.load_flare_catalogue_range(
            "2024-01-01", "2024-01-03"
        )
        required = {"time_begin", "time_max", "time_end", "class_type", "class_num"}
        assert required.issubset(set(df.columns))
        non_empty = df.loc[df["class_type"] != "", "class_type"]
        if len(non_empty) > 0:
            assert all(len(ct) == 1 for ct in non_empty)


class TestHalfOpenInterval:
    def test_range_filters_to_half_open_interval(self, fake_fetch):
        """Records at exactly ``end`` must be excluded; those at ``start`` included."""
        # _FAKE_XRAY has records at 2024-01-01T12:00, 2024-01-02T12:00,
        # and 2024-01-03T00:00.  Requesting [2024-01-01, 2024-01-03) means
        # the record at 2024-01-03T00:00:00Z must be excluded.
        df = data_loader.load_goes_xray_range("2024-01-01", "2024-01-03")
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 3, tzinfo=timezone.utc)

        assert all(t >= start for t in df["time"])
        assert all(t < end for t in df["time"])
