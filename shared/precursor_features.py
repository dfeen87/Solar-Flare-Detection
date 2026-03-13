"""
shared.precursor_features — ΔΦ(t) precursor operator utilities.

Provides a reusable backward-difference operator for scalar time series Φ(t):

    ΔΦ(tᵢ) = Φ(tᵢ) − Φ(tⱼ)

where tⱼ is the latest time satisfying tⱼ ≤ tᵢ − Δt.

If no such tⱼ exists, or if either value is NaN, ΔΦ(tᵢ) = NaN.
"""

import numpy as np
import pandas as pd


def _compute_backward_difference(
    times: pd.Series,
    values: pd.Series,
    delta: pd.Timedelta,
) -> np.ndarray:
    """Return ΔΦ(tᵢ) for each sample using a backward finite difference.

    Parameters
    ----------
    times:
        UTC Timestamp series, sorted ascending.
    values:
        Float series Φ(tᵢ), same length as *times*.
    delta:
        Positive time offset Δt.

    Returns
    -------
    numpy.ndarray
        Array of ΔΦ(tᵢ) values (float64, NaN where undefined).
    """
    times_arr = times.to_numpy(dtype="datetime64[ns]")
    values_arr = values.to_numpy(dtype=float)
    n = len(times_arr)
    result = np.full(n, np.nan)

    delta_ns = int(delta.total_seconds() * 1e9)

    for i in range(n):
        target = times_arr[i] - np.timedelta64(delta_ns, "ns")
        # searchsorted finds insertion point for target in sorted times_arr;
        # the latest index j with times_arr[j] <= target is (insertion_point - 1).
        j = np.searchsorted(times_arr, target, side="right") - 1
        if j >= 0:
            phi_i = values_arr[i]
            phi_j = values_arr[j]
            if np.isfinite(phi_i) and np.isfinite(phi_j):
                result[i] = phi_i - phi_j

    return result


def compute_delta_phi(
    df: pd.DataFrame,
    *,
    time_col: str = "time",
    value_col: str = "phi",
    delta: pd.Timedelta = pd.Timedelta(hours=1),
) -> pd.DataFrame:
    """Compute the backward-difference ΔΦ(t) for a scalar time series.

    Parameters
    ----------
    df:
        Input DataFrame containing at least *time_col* and *value_col*.
    time_col:
        Name of the datetime column (converted to UTC internally).
    value_col:
        Name of the scalar Φ(t) column.
    delta:
        Positive time offset Δt (default: 1 hour).

    Returns
    -------
    pandas.DataFrame
        New DataFrame with columns ``["time", "phi", "delta_phi"]``, sorted
        by ``time`` ascending.  ``delta_phi`` is NaN where undefined.

    Raises
    ------
    ValueError
        If *time_col* or *value_col* is absent, or if *delta* ≤ 0.
    """
    if time_col not in df.columns:
        raise ValueError(f"df must contain column: '{time_col}'")
    if value_col not in df.columns:
        raise ValueError(f"df must contain column: '{value_col}'")
    if delta <= pd.Timedelta(0):
        raise ValueError("delta must be a positive pandas.Timedelta")

    if df.empty:
        return pd.DataFrame(columns=["time", "phi", "delta_phi"])

    work = df[[time_col, value_col]].copy()
    work[time_col] = pd.to_datetime(work[time_col], utc=True)
    work = work.sort_values(time_col).reset_index(drop=True)

    delta_phi = _compute_backward_difference(work[time_col], work[value_col], delta)

    return pd.DataFrame(
        {
            "time": work[time_col].values,
            "phi": work[value_col].values,
            "delta_phi": delta_phi,
        }
    )
