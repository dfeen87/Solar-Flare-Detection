"""
test_precursor_features.py — unit tests for shared.precursor_features.

Tests cover:
  A. Basic backward difference with regular sampling
  B. Irregular sampling with latest tⱼ ≤ tᵢ − Δt
  C. NaN handling
  D. Column name flexibility and error messages
  E. Delta validation
  F. Empty DataFrame
"""

import numpy as np
import pandas as pd
import pytest

from shared.precursor_features import compute_delta_phi

t0 = pd.Timestamp("2026-01-01T00:00:00Z")


# ---------------------------------------------------------------------------
# A. Basic backward difference with regular 1-minute sampling
# ---------------------------------------------------------------------------

def test_regular_sampling_basic():
    n = 10
    time = t0 + pd.to_timedelta(np.arange(n), unit="min")
    phi = np.arange(n, dtype=float)
    df = pd.DataFrame({"time": time, "phi": phi})

    result = compute_delta_phi(df, delta=pd.Timedelta(minutes=5))

    assert list(result.columns) == ["time", "phi", "delta_phi"]
    assert len(result) == n

    # First 5 samples have no sufficient history → NaN
    assert np.all(np.isnan(result["delta_phi"].values[:5]))

    # Samples 5–9: ΔΦ = i − (i−5) = 5
    assert np.allclose(result["delta_phi"].values[5:], 5.0)


# ---------------------------------------------------------------------------
# B. Irregular sampling — latest tⱼ ≤ tᵢ − Δt
# ---------------------------------------------------------------------------

def test_irregular_sampling():
    offsets = [0, 3, 7, 12]  # minutes
    time = [t0 + pd.Timedelta(minutes=m) for m in offsets]
    phi = [1.0, 2.0, 4.0, 7.0]
    df = pd.DataFrame({"time": time, "phi": phi})

    result = compute_delta_phi(df, delta=pd.Timedelta(minutes=5))
    dphi = result["delta_phi"].values

    # t0 (0 min): no history → NaN
    assert np.isnan(dphi[0])
    # t1 (3 min): need tⱼ ≤ -2 min → none → NaN
    assert np.isnan(dphi[1])
    # t2 (7 min): tⱼ ≤ 2 min → latest is t0 → 4.0 - 1.0 = 3.0
    assert dphi[2] == pytest.approx(3.0)
    # t3 (12 min): tⱼ ≤ 7 min → latest is t2 → 7.0 - 4.0 = 3.0
    assert dphi[3] == pytest.approx(3.0)


# ---------------------------------------------------------------------------
# C. NaN handling
# ---------------------------------------------------------------------------

def test_nan_handling():
    n = 5
    time = t0 + pd.to_timedelta(np.arange(n), unit="min")
    phi = np.array([0.0, 1.0, np.nan, 3.0, 4.0])
    df = pd.DataFrame({"time": time, "phi": phi})

    result = compute_delta_phi(df, delta=pd.Timedelta(minutes=2))
    dphi = result["delta_phi"].values

    # i=0,1: insufficient history → NaN
    assert np.isnan(dphi[0])
    assert np.isnan(dphi[1])

    # i=2 (t=2): Φ(2) = NaN → ΔΦ = NaN
    assert np.isnan(dphi[2])

    # i=3 (t=3): tⱼ ≤ 1 min → j=1, Φ(1)=1.0, Φ(3)=3.0 → 3.0-1.0=2.0
    assert dphi[3] == pytest.approx(2.0)

    # i=4 (t=4): tⱼ ≤ 2 min → j=2, Φ(2)=NaN → ΔΦ = NaN
    assert np.isnan(dphi[4])


# ---------------------------------------------------------------------------
# D. Column name flexibility and error messages
# ---------------------------------------------------------------------------

def test_custom_column_names():
    n = 6
    time = t0 + pd.to_timedelta(np.arange(n), unit="min")
    value = np.arange(n, dtype=float)
    df = pd.DataFrame({"timestamp": time, "value": value})

    result = compute_delta_phi(
        df,
        time_col="timestamp",
        value_col="value",
        delta=pd.Timedelta(minutes=3),
    )

    assert list(result.columns) == ["time", "phi", "delta_phi"]
    assert len(result) == n

    # First 3 samples have insufficient history → NaN
    assert np.all(np.isnan(result["delta_phi"].values[:3]))
    # Samples 3–5: ΔΦ = i − (i−3) = 3.0
    assert np.allclose(result["delta_phi"].values[3:], 3.0)


def test_missing_time_col_raises():
    df = pd.DataFrame({"phi": [1.0, 2.0]})
    with pytest.raises(ValueError, match="df must contain column: 'time'"):
        compute_delta_phi(df)


def test_missing_value_col_raises():
    df = pd.DataFrame({"time": [t0, t0 + pd.Timedelta(minutes=1)]})
    with pytest.raises(ValueError, match="df must contain column: 'phi'"):
        compute_delta_phi(df)


def test_missing_custom_time_col_raises():
    df = pd.DataFrame({"value": [1.0, 2.0]})
    with pytest.raises(ValueError, match="df must contain column: 'ts'"):
        compute_delta_phi(df, time_col="ts", value_col="value")


def test_missing_custom_value_col_raises():
    df = pd.DataFrame({"timestamp": [t0]})
    with pytest.raises(ValueError, match="df must contain column: 'val'"):
        compute_delta_phi(df, time_col="timestamp", value_col="val")


# ---------------------------------------------------------------------------
# E. Delta validation
# ---------------------------------------------------------------------------

def test_zero_delta_raises():
    df = pd.DataFrame({"time": [t0], "phi": [1.0]})
    with pytest.raises(ValueError, match="delta must be a positive pandas.Timedelta"):
        compute_delta_phi(df, delta=pd.Timedelta(0))


def test_negative_delta_raises():
    df = pd.DataFrame({"time": [t0], "phi": [1.0]})
    with pytest.raises(ValueError, match="delta must be a positive pandas.Timedelta"):
        compute_delta_phi(df, delta=pd.Timedelta(minutes=-1))


# ---------------------------------------------------------------------------
# F. Empty DataFrame
# ---------------------------------------------------------------------------

def test_empty_dataframe():
    df = pd.DataFrame({"time": pd.Series([], dtype="datetime64[ns]"), "phi": pd.Series([], dtype=float)})
    result = compute_delta_phi(df)

    assert list(result.columns) == ["time", "phi", "delta_phi"]
    assert len(result) == 0
