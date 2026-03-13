"""
test_composite_features.py — unit tests for shared.composite_features.

Tests cover:
  A. Basic alignment with staggered timestamps
  B. Column name flexibility
  C. Missing column errors
  D. Empty inputs
  E. UTC enforcement for naive timestamps
  F. Deterministic ordering with shuffled inputs
"""

import numpy as np
import pandas as pd
import pytest

from shared.composite_features import assemble_precursor_features

t0 = pd.Timestamp("2026-01-01T00:00:00Z")


# ---------------------------------------------------------------------------
# A. Basic alignment
# ---------------------------------------------------------------------------

def test_basic_alignment():
    """ΔΦ at [0,1,2], X-ray at [1,2,3], EUV at [2,3,4] → grid [0,1,2,3,4]."""
    delta_phi_df = pd.DataFrame({
        "time": [t0, t0 + pd.Timedelta(minutes=1), t0 + pd.Timedelta(minutes=2)],
        "delta_phi": [1.0, 2.0, 3.0],
    })
    xray_df = pd.DataFrame({
        "time": [t0 + pd.Timedelta(minutes=1), t0 + pd.Timedelta(minutes=2), t0 + pd.Timedelta(minutes=3)],
        "xray": [10.0, 20.0, 30.0],
    })
    euv_df = pd.DataFrame({
        "time": [t0 + pd.Timedelta(minutes=2), t0 + pd.Timedelta(minutes=3), t0 + pd.Timedelta(minutes=4)],
        "euv": [100.0, 200.0, 300.0],
    })

    result = assemble_precursor_features(
        delta_phi_df=delta_phi_df,
        xray_df=xray_df,
        euv_df=euv_df,
    )

    assert list(result.columns) == ["time", "delta_phi", "xray", "euv"]
    assert len(result) == 5

    times = result["time"].tolist()
    expected_times = [t0 + pd.Timedelta(minutes=i) for i in range(5)]
    # Compare as UTC timestamps
    for actual, expected in zip(times, expected_times):
        assert pd.Timestamp(actual) == pd.Timestamp(expected).tz_localize("UTC") if pd.Timestamp(expected).tzinfo is None else pd.Timestamp(expected)

    dphi = result["delta_phi"].values
    xray = result["xray"].values
    euv = result["euv"].values

    # minute 0: delta_phi=1.0, xray=NaN, euv=NaN
    assert dphi[0] == pytest.approx(1.0)
    assert np.isnan(xray[0])
    assert np.isnan(euv[0])

    # minute 1: delta_phi=2.0, xray=10.0, euv=NaN
    assert dphi[1] == pytest.approx(2.0)
    assert xray[1] == pytest.approx(10.0)
    assert np.isnan(euv[1])

    # minute 2: delta_phi=3.0, xray=20.0, euv=100.0
    assert dphi[2] == pytest.approx(3.0)
    assert xray[2] == pytest.approx(20.0)
    assert euv[2] == pytest.approx(100.0)

    # minute 3: delta_phi=NaN, xray=30.0, euv=200.0
    assert np.isnan(dphi[3])
    assert xray[3] == pytest.approx(30.0)
    assert euv[3] == pytest.approx(200.0)

    # minute 4: delta_phi=NaN, xray=NaN, euv=300.0
    assert np.isnan(dphi[4])
    assert np.isnan(xray[4])
    assert euv[4] == pytest.approx(300.0)


# ---------------------------------------------------------------------------
# B. Column name flexibility
# ---------------------------------------------------------------------------

def test_column_name_flexibility():
    """Custom time_col and value column names should work correctly."""
    delta_phi_df = pd.DataFrame({
        "ts": [t0, t0 + pd.Timedelta(minutes=1)],
        "dp": [5.0, 6.0],
    })
    xray_df = pd.DataFrame({
        "ts": [t0 + pd.Timedelta(minutes=1), t0 + pd.Timedelta(minutes=2)],
        "flux": [50.0, 60.0],
    })
    euv_df = pd.DataFrame({
        "ts": [t0, t0 + pd.Timedelta(minutes=2)],
        "intensity": [500.0, 600.0],
    })

    result = assemble_precursor_features(
        delta_phi_df=delta_phi_df,
        xray_df=xray_df,
        euv_df=euv_df,
        time_col="ts",
        delta_phi_col="dp",
        xray_col="flux",
        euv_col="intensity",
    )

    assert list(result.columns) == ["time", "delta_phi", "xray", "euv"]
    assert len(result) == 3

    # minute 0: delta_phi=5.0, xray=NaN, euv=500.0
    assert result["delta_phi"].iloc[0] == pytest.approx(5.0)
    assert np.isnan(result["xray"].iloc[0])
    assert result["euv"].iloc[0] == pytest.approx(500.0)

    # minute 1: delta_phi=6.0, xray=50.0, euv=NaN
    assert result["delta_phi"].iloc[1] == pytest.approx(6.0)
    assert result["xray"].iloc[1] == pytest.approx(50.0)
    assert np.isnan(result["euv"].iloc[1])

    # minute 2: delta_phi=NaN, xray=60.0, euv=600.0
    assert np.isnan(result["delta_phi"].iloc[2])
    assert result["xray"].iloc[2] == pytest.approx(60.0)
    assert result["euv"].iloc[2] == pytest.approx(600.0)


# ---------------------------------------------------------------------------
# C. Missing column errors
# ---------------------------------------------------------------------------

def _make_valid_dfs():
    delta_phi_df = pd.DataFrame({"time": [t0], "delta_phi": [1.0]})
    xray_df = pd.DataFrame({"time": [t0], "xray": [10.0]})
    euv_df = pd.DataFrame({"time": [t0], "euv": [100.0]})
    return delta_phi_df, xray_df, euv_df


def test_missing_time_col_delta_phi_raises():
    _, xray_df, euv_df = _make_valid_dfs()
    delta_phi_df = pd.DataFrame({"delta_phi": [1.0]})
    with pytest.raises(ValueError, match="delta_phi_df must contain column: 'time'"):
        assemble_precursor_features(
            delta_phi_df=delta_phi_df,
            xray_df=xray_df,
            euv_df=euv_df,
        )


def test_missing_value_col_delta_phi_raises():
    _, xray_df, euv_df = _make_valid_dfs()
    delta_phi_df = pd.DataFrame({"time": [t0]})
    with pytest.raises(ValueError, match="delta_phi_df must contain column: 'delta_phi'"):
        assemble_precursor_features(
            delta_phi_df=delta_phi_df,
            xray_df=xray_df,
            euv_df=euv_df,
        )


def test_missing_time_col_xray_raises():
    delta_phi_df, _, euv_df = _make_valid_dfs()
    xray_df = pd.DataFrame({"xray": [10.0]})
    with pytest.raises(ValueError, match="xray_df must contain column: 'time'"):
        assemble_precursor_features(
            delta_phi_df=delta_phi_df,
            xray_df=xray_df,
            euv_df=euv_df,
        )


def test_missing_value_col_xray_raises():
    delta_phi_df, _, euv_df = _make_valid_dfs()
    xray_df = pd.DataFrame({"time": [t0]})
    with pytest.raises(ValueError, match="xray_df must contain column: 'xray'"):
        assemble_precursor_features(
            delta_phi_df=delta_phi_df,
            xray_df=xray_df,
            euv_df=euv_df,
        )


def test_missing_time_col_euv_raises():
    delta_phi_df, xray_df, _ = _make_valid_dfs()
    euv_df = pd.DataFrame({"euv": [100.0]})
    with pytest.raises(ValueError, match="euv_df must contain column: 'time'"):
        assemble_precursor_features(
            delta_phi_df=delta_phi_df,
            xray_df=xray_df,
            euv_df=euv_df,
        )


def test_missing_value_col_euv_raises():
    delta_phi_df, xray_df, _ = _make_valid_dfs()
    euv_df = pd.DataFrame({"time": [t0]})
    with pytest.raises(ValueError, match="euv_df must contain column: 'euv'"):
        assemble_precursor_features(
            delta_phi_df=delta_phi_df,
            xray_df=xray_df,
            euv_df=euv_df,
        )


# ---------------------------------------------------------------------------
# D. Empty inputs
# ---------------------------------------------------------------------------

def test_all_empty_returns_empty_schema():
    """All-empty inputs return an empty DataFrame with the correct schema."""
    empty_dp = pd.DataFrame({"time": pd.Series([], dtype="datetime64[ns]"), "delta_phi": pd.Series([], dtype=float)})
    empty_xr = pd.DataFrame({"time": pd.Series([], dtype="datetime64[ns]"), "xray": pd.Series([], dtype=float)})
    empty_euv = pd.DataFrame({"time": pd.Series([], dtype="datetime64[ns]"), "euv": pd.Series([], dtype=float)})

    result = assemble_precursor_features(
        delta_phi_df=empty_dp,
        xray_df=empty_xr,
        euv_df=empty_euv,
    )

    assert list(result.columns) == ["time", "delta_phi", "xray", "euv"]
    assert len(result) == 0


def test_one_empty_input_still_aligns():
    """One empty input still produces a correct alignment."""
    delta_phi_df = pd.DataFrame({
        "time": [t0, t0 + pd.Timedelta(minutes=1)],
        "delta_phi": [1.0, 2.0],
    })
    xray_df = pd.DataFrame({
        "time": [t0],
        "xray": [10.0],
    })
    empty_euv = pd.DataFrame({"time": pd.Series([], dtype="datetime64[ns]"), "euv": pd.Series([], dtype=float)})

    result = assemble_precursor_features(
        delta_phi_df=delta_phi_df,
        xray_df=xray_df,
        euv_df=empty_euv,
    )

    assert list(result.columns) == ["time", "delta_phi", "xray", "euv"]
    assert len(result) == 2

    assert result["delta_phi"].iloc[0] == pytest.approx(1.0)
    assert result["xray"].iloc[0] == pytest.approx(10.0)
    assert np.isnan(result["euv"].iloc[0])

    assert result["delta_phi"].iloc[1] == pytest.approx(2.0)
    assert np.isnan(result["xray"].iloc[1])
    assert np.isnan(result["euv"].iloc[1])


# ---------------------------------------------------------------------------
# E. UTC enforcement
# ---------------------------------------------------------------------------

def test_naive_timestamps_converted_to_utc():
    """Naive timestamps in inputs should be treated as UTC in the output."""
    delta_phi_df = pd.DataFrame({
        "time": [pd.Timestamp("2026-01-01 00:00:00"), pd.Timestamp("2026-01-01 00:01:00")],
        "delta_phi": [1.0, 2.0],
    })
    xray_df = pd.DataFrame({
        "time": [pd.Timestamp("2026-01-01 00:01:00")],
        "xray": [10.0],
    })
    euv_df = pd.DataFrame({
        "time": [pd.Timestamp("2026-01-01 00:02:00")],
        "euv": [100.0],
    })

    result = assemble_precursor_features(
        delta_phi_df=delta_phi_df,
        xray_df=xray_df,
        euv_df=euv_df,
    )

    # Output timestamps must be UTC-aware
    utc = pd.Timestamp("2026-01-01", tz="UTC").tzinfo
    for ts in result["time"]:
        assert pd.Timestamp(ts).tzinfo is not None
        assert pd.Timestamp(ts).tzinfo == utc


# ---------------------------------------------------------------------------
# F. Deterministic ordering
# ---------------------------------------------------------------------------

def test_shuffled_inputs_produce_sorted_output():
    """Shuffled input rows should produce output sorted ascending by time."""
    times = [t0 + pd.Timedelta(minutes=i) for i in range(5)]

    delta_phi_df = pd.DataFrame({
        "time": times[::-1],  # reverse order
        "delta_phi": [5.0, 4.0, 3.0, 2.0, 1.0],
    })
    xray_df = pd.DataFrame({
        "time": [times[2], times[0], times[4], times[1], times[3]],  # shuffled
        "xray": [30.0, 10.0, 50.0, 20.0, 40.0],
    })
    euv_df = pd.DataFrame({
        "time": [times[4], times[2], times[0]],
        "euv": [500.0, 300.0, 100.0],
    })

    result = assemble_precursor_features(
        delta_phi_df=delta_phi_df,
        xray_df=xray_df,
        euv_df=euv_df,
    )

    assert len(result) == 5

    result_times = result["time"].tolist()
    for i in range(len(result_times) - 1):
        assert pd.Timestamp(result_times[i]) < pd.Timestamp(result_times[i + 1])

    # Verify values are correctly placed after sorting
    assert result["delta_phi"].iloc[0] == pytest.approx(1.0)
    assert result["xray"].iloc[0] == pytest.approx(10.0)
    assert result["euv"].iloc[0] == pytest.approx(100.0)
