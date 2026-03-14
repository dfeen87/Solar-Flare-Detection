"""
event_evaluation — Event-based evaluation metrics for solar-flare precursor signals.

Public API
----------
compute_lead_times(signal_df, flare_df, *, window_hours=24)
compute_threshold_metrics(signal_df, flare_df, thresholds)
compute_roc(signal_df, flare_df, thresholds)
compute_auc(fpr, tpr)
align_flare_onsets(flare_df, delta_phi_df, *, time_col="time")
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Input validation helpers
# ---------------------------------------------------------------------------

def _validate_signal_df(signal_df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with UTC-parsed *time* and float *signal*."""
    if not {"time", "signal"}.issubset(signal_df.columns):
        raise ValueError("signal_df must contain columns: {'time','signal'}")
    df = signal_df[["time", "signal"]].copy()
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df["signal"] = df["signal"].astype(float)
    return df


def _validate_flare_df(flare_df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with UTC-parsed *onset_time*."""
    if "onset_time" not in flare_df.columns:
        raise ValueError("flare_df must contain column: 'onset_time'")
    df = flare_df[["onset_time"]].copy()
    df["onset_time"] = pd.to_datetime(df["onset_time"], utc=True)
    return df


def _validate_thresholds(thresholds):
    """Return *thresholds* as a 1-D float numpy array; raise on empty."""
    arr = np.asarray(thresholds, dtype=float).ravel()
    if arr.size == 0:
        raise ValueError("thresholds must be a non-empty 1D array-like")
    return arr


# ---------------------------------------------------------------------------
# Internal helper: flare-aligned window extraction
# ---------------------------------------------------------------------------

def _extract_flare_windows(
    signal_df: pd.DataFrame,
    flare_df: pd.DataFrame,
    W_pre: pd.Timedelta = pd.Timedelta(hours=24),
    W_post: pd.Timedelta = pd.Timedelta(hours=2),
) -> list[pd.DataFrame]:
    """Return a list of signal windows aligned to each flare onset.

    For each flare onset *t_k* the window is ``[t_k - W_pre, t_k + W_post)``
    (left-closed, right-open).
    """
    sig = _validate_signal_df(signal_df).sort_values("time").reset_index(drop=True)
    flares = _validate_flare_df(flare_df)

    windows: list[pd.DataFrame] = []
    for onset in flares["onset_time"]:
        start = onset - W_pre
        end = onset + W_post
        mask = (sig["time"] >= start) & (sig["time"] < end)
        chunk = sig.loc[mask, ["time", "signal"]].reset_index(drop=True)
        if chunk.empty:
            chunk = pd.DataFrame(columns=["time", "signal"])
        windows.append(chunk)
    return windows


# ---------------------------------------------------------------------------
# Public: compute_lead_times
# ---------------------------------------------------------------------------

def compute_lead_times(
    signal_df: pd.DataFrame,
    flare_df: pd.DataFrame,
    *,
    window_hours: int | float = 24,
) -> pd.DataFrame:
    """Compute precursor lead times for each flare onset.

    Returns a DataFrame with one row per flare and columns:
        onset_time, lead_time_first_crossing_hours, lead_time_max_signal_hours,
        first_crossing_time, max_signal_time
    """
    threshold = 0.5
    sig = _validate_signal_df(signal_df).sort_values("time").reset_index(drop=True)
    flares = _validate_flare_df(flare_df)

    W = pd.Timedelta(hours=window_hours)

    rows: list[dict] = []
    for onset in flares["onset_time"]:
        start = onset - W
        mask = (sig["time"] >= start) & (sig["time"] < onset)
        window = sig.loc[mask].reset_index(drop=True)

        # Drop NaN signals
        window = window.dropna(subset=["signal"]).reset_index(drop=True)

        row: dict = {"onset_time": onset}

        if window.empty:
            row["lead_time_first_crossing_hours"] = np.nan
            row["lead_time_max_signal_hours"] = np.nan
            row["first_crossing_time"] = pd.NaT
            row["max_signal_time"] = pd.NaT
            rows.append(row)
            continue

        # --- First crossing mode ---
        signals = window["signal"].to_numpy()
        times = window["time"].to_numpy()
        crossing_time = None
        for i in range(len(signals)):
            if signals[i] >= threshold:
                if i == 0:
                    # edge-start crossing
                    crossing_time = times[i]
                    break
                elif signals[i - 1] < threshold:
                    crossing_time = times[i]
                    break

        if crossing_time is not None:
            crossing_ts = pd.Timestamp(crossing_time)
            row["first_crossing_time"] = crossing_ts
            row["lead_time_first_crossing_hours"] = (
                (onset - crossing_ts).total_seconds() / 3600.0
            )
        else:
            row["first_crossing_time"] = pd.NaT
            row["lead_time_first_crossing_hours"] = np.nan

        # --- Max signal mode ---
        max_val = window["signal"].max()
        # Pick latest time among equal maxima
        max_mask = window["signal"] == max_val
        max_time = window.loc[max_mask, "time"].iloc[-1]
        row["max_signal_time"] = max_time
        row["lead_time_max_signal_hours"] = (
            (onset - max_time).total_seconds() / 3600.0
        )

        rows.append(row)

    _cols = [
        "onset_time",
        "lead_time_first_crossing_hours",
        "lead_time_max_signal_hours",
        "first_crossing_time",
        "max_signal_time",
    ]
    if not rows:
        return pd.DataFrame(columns=_cols)
    result = pd.DataFrame(rows)
    # Ensure column order
    return result[_cols]


# ---------------------------------------------------------------------------
# Public: compute_threshold_metrics
# ---------------------------------------------------------------------------

def compute_threshold_metrics(
    signal_df: pd.DataFrame,
    flare_df: pd.DataFrame,
    thresholds,
) -> pd.DataFrame:
    """Compute event-based confusion counts and rates for each threshold.

    Returns a DataFrame with columns:
        threshold, TP, FP, TN, FN, TPR, FPR, FNR, TNR
    """
    sig = _validate_signal_df(signal_df).sort_values("time").reset_index(drop=True)
    flares = _validate_flare_df(flare_df)
    thresholds_arr = _validate_thresholds(thresholds)

    pre_window = pd.Timedelta(hours=24)

    # Build boolean mask: True if timestamp is inside any flare pre-window
    in_pre_window = np.zeros(len(sig), dtype=bool)
    for onset in flares["onset_time"]:
        start = onset - pre_window
        mask = (sig["time"] >= start) & (sig["time"] < onset)
        in_pre_window |= mask.to_numpy()

    # Pre-compute per-flare window indices
    flare_windows: list[np.ndarray] = []
    for onset in flares["onset_time"]:
        start = onset - pre_window
        mask = (sig["time"] >= start) & (sig["time"] < onset)
        flare_windows.append(sig.loc[mask, "signal"].to_numpy())

    non_flare_signals = sig.loc[~in_pre_window, "signal"].to_numpy()
    non_flare_valid = non_flare_signals[~np.isnan(non_flare_signals)]

    rows: list[dict] = []
    for theta in thresholds_arr:
        tp = 0
        fn = 0
        for win_signals in flare_windows:
            valid = win_signals[~np.isnan(win_signals)]
            if np.any(valid >= theta):
                tp += 1
            else:
                fn += 1

        fp = int(np.sum(non_flare_valid >= theta))
        tn = int(np.sum(non_flare_valid < theta))

        tp_fn = tp + fn
        fp_tn = fp + tn

        row = {
            "threshold": theta,
            "TP": int(tp),
            "FP": int(fp),
            "TN": int(tn),
            "FN": int(fn),
            "TPR": tp / tp_fn if tp_fn > 0 else np.nan,
            "FPR": fp / fp_tn if fp_tn > 0 else np.nan,
            "FNR": fn / tp_fn if tp_fn > 0 else np.nan,
            "TNR": tn / fp_tn if fp_tn > 0 else np.nan,
        }
        rows.append(row)

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Public: compute_roc
# ---------------------------------------------------------------------------

def compute_roc(
    signal_df: pd.DataFrame,
    flare_df: pd.DataFrame,
    thresholds,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (fpr_sorted, tpr_sorted, thresholds_sorted) for an ROC curve."""
    thresholds_arr = _validate_thresholds(thresholds)
    metrics = compute_threshold_metrics(signal_df, flare_df, thresholds_arr)

    fpr = metrics["FPR"].to_numpy(dtype=float)
    tpr = metrics["TPR"].to_numpy(dtype=float)

    order = np.argsort(fpr, kind="mergesort")
    return fpr[order], tpr[order], thresholds_arr[order]


# ---------------------------------------------------------------------------
# Public: compute_auc
# ---------------------------------------------------------------------------

def compute_auc(fpr, tpr) -> float:
    """Compute trapezoidal AUC from FPR / TPR arrays."""
    fpr_arr = np.asarray(fpr, dtype=float).ravel()
    tpr_arr = np.asarray(tpr, dtype=float).ravel()

    if fpr_arr.shape != tpr_arr.shape or fpr_arr.ndim != 1:
        raise ValueError("fpr and tpr must be 1D arrays of the same length >= 2")
    if fpr_arr.size < 2:
        raise ValueError("fpr and tpr must be 1D arrays of the same length >= 2")

    # Drop NaN pairs
    valid = ~(np.isnan(fpr_arr) | np.isnan(tpr_arr))
    fpr_arr = fpr_arr[valid]
    tpr_arr = tpr_arr[valid]
    if fpr_arr.size < 2:
        return np.nan

    # Ensure non-decreasing FPR
    if not np.all(np.diff(fpr_arr) >= 0):
        order = np.argsort(fpr_arr, kind="mergesort")
        fpr_arr = fpr_arr[order]
        tpr_arr = tpr_arr[order]

    return float(np.trapezoid(tpr_arr, fpr_arr))


# ---------------------------------------------------------------------------
# Public: align_flare_onsets
# ---------------------------------------------------------------------------

def align_flare_onsets(
    flare_df: pd.DataFrame,
    delta_phi_df: pd.DataFrame,
    *,
    time_col: str = "time",
) -> pd.DataFrame:
    """Align flare onset times with the ΔΦ(t) timeline.

    For each flare onset *t_k*, finds the nearest timestamp in the ΔΦ(t)
    series and attaches the corresponding ΔΦ value.

    Parameters
    ----------
    flare_df : pd.DataFrame
        Must contain ``"onset_time"`` column (UTC-aware or parseable).
    delta_phi_df : pd.DataFrame
        Must contain *time_col* (UTC timestamp) and ``"delta_phi"`` columns.
    time_col : str, optional
        Name of the timestamp column in *delta_phi_df*.  Default ``"time"``.

    Returns
    -------
    pd.DataFrame
        Columns: ``onset_time``, ``aligned_time``, ``delta_phi_at_onset``.
        One row per flare onset; ``aligned_time`` is the nearest ΔΦ(t)
        timestamp; ``delta_phi_at_onset`` is the corresponding ΔΦ value.

    Raises
    ------
    ValueError
        If required columns are missing.

    Notes
    -----
    When *delta_phi_df* is empty, ``aligned_time`` is NaT and
    ``delta_phi_at_onset`` is NaN for every flare.

    References
    ----------
    PAPER.md §12.2 — precursor-window alignment.
    """
    if "onset_time" not in flare_df.columns:
        raise ValueError("flare_df must contain column: 'onset_time'")
    if time_col not in delta_phi_df.columns:
        raise ValueError(f"delta_phi_df must contain column: '{time_col}'")
    if "delta_phi" not in delta_phi_df.columns:
        raise ValueError("delta_phi_df must contain column: 'delta_phi'")

    flares = flare_df[["onset_time"]].copy()
    flares["onset_time"] = pd.to_datetime(flares["onset_time"], utc=True)

    sig = delta_phi_df[[time_col, "delta_phi"]].copy()
    sig[time_col] = pd.to_datetime(sig[time_col], utc=True)
    sig = sig.sort_values(time_col).reset_index(drop=True)

    _cols = ["onset_time", "aligned_time", "delta_phi_at_onset"]
    if sig.empty:
        result = flares.copy()
        result["aligned_time"] = pd.NaT
        result["delta_phi_at_onset"] = np.nan
        return result[_cols].reset_index(drop=True)

    sig_times = sig[time_col].to_numpy(dtype="datetime64[ns]")
    sig_values = sig["delta_phi"].to_numpy(dtype=float)

    rows: list[dict] = []
    for onset in flares["onset_time"]:
        onset_ns = onset.to_datetime64().astype("datetime64[ns]")
        idx = int(np.searchsorted(sig_times, onset_ns, side="left"))
        idx = min(idx, len(sig_times) - 1)
        if idx > 0:
            diff_prev = abs(
                (sig_times[idx - 1] - onset_ns).astype("int64")
            )
            diff_curr = abs(
                (sig_times[idx] - onset_ns).astype("int64")
            )
            if diff_prev < diff_curr:
                idx = idx - 1
        rows.append({
            "onset_time": onset,
            "aligned_time": pd.Timestamp(sig_times[idx]),
            "delta_phi_at_onset": float(sig_values[idx]),
        })

    if not rows:
        return pd.DataFrame(columns=_cols)
    return pd.DataFrame(rows)[_cols]
