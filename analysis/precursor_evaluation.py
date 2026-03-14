"""
precursor_evaluation — End-to-end evaluation of precursor signals using
event-based metrics.

Public API
----------
evaluate_precursor(
    *,
    feature_df,
    flare_df,
    time_col="time",
    value_col="delta_phi",
    thresholds,
) -> dict[str, pd.DataFrame | np.ndarray | float]

evaluate_precursor_window(
    *,
    feature_df,
    flare_df,
    time_col="time",
    value_col="delta_phi",
    pre_window_start_hours=24,
    pre_window_end_hours=6,
    thresholds,
) -> dict[str, pd.DataFrame | np.ndarray | float]

Mathematical definitions
------------------------
Let S(tᵢ) be the precursor signal and tₖ the flare onset times.

For threshold θ the evaluation computes:
  - lead-time distributions (first crossing + max-signal modes)
  - confusion counts TP / FP / TN / FN and derived rates
  - TPR / FPR curves
  - AUC via trapezoidal integration

All definitions match the existing event-based evaluation layer
(shared/event_evaluation.py).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from shared.event_evaluation import (
    compute_auc,
    compute_lead_times,
    compute_roc,
    compute_threshold_metrics,
)


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _prepare_signal_df(
    feature_df: pd.DataFrame,
    time_col: str,
    value_col: str,
) -> pd.DataFrame:
    """Return a two-column DataFrame with columns ``["time", "signal"]``.

    Steps
    -----
    1. Validates that *time_col* and *value_col* are present.
    2. Converts *time_col* to UTC-aware timestamps.
    3. Drops rows where *value_col* is NaN.
    4. Sorts ascending by time.
    5. Renames *time_col* → ``"time"``, *value_col* → ``"signal"``.
    """
    if time_col not in feature_df.columns:
        raise ValueError(
            f"feature_df must contain column: '{time_col}'"
        )
    if value_col not in feature_df.columns:
        raise ValueError(
            f"feature_df must contain column: '{value_col}'"
        )

    df = feature_df[[time_col, value_col]].copy()
    df[time_col] = pd.to_datetime(df[time_col], utc=True)
    df = df.dropna(subset=[value_col])
    df = df.sort_values(time_col).reset_index(drop=True)
    df = df.rename(columns={time_col: "time", value_col: "signal"})
    return df


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate_precursor(
    *,
    feature_df: pd.DataFrame,
    flare_df: pd.DataFrame,
    time_col: str = "time",
    value_col: str = "delta_phi",
    thresholds: "np.ndarray | list[float]",
) -> "dict[str, pd.DataFrame | np.ndarray | float]":
    """Run the full event-based evaluation pipeline on a precursor signal.

    Parameters
    ----------
    feature_df : pd.DataFrame
        Must contain *time_col* and *value_col*.
    flare_df : pd.DataFrame
        Must contain ``"onset_time"``.
    time_col : str, optional
        Name of the timestamp column in *feature_df*.  Default ``"time"``.
    value_col : str, optional
        Name of the signal column in *feature_df*.  Default ``"delta_phi"``.
    thresholds : array-like of float
        Non-empty 1D sequence of threshold values for the evaluation sweep.

    Returns
    -------
    dict with keys:
        ``"lead_times"``       – :class:`pd.DataFrame` (one row per flare)
        ``"threshold_metrics"`` – :class:`pd.DataFrame` (one row per threshold)
        ``"roc_fpr"``          – :class:`np.ndarray`
        ``"roc_tpr"``          – :class:`np.ndarray`
        ``"roc_thresholds"``   – :class:`np.ndarray`
        ``"auc"``              – float

    Raises
    ------
    ValueError
        If *feature_df* is missing *time_col* or *value_col*, if *flare_df* is
        missing ``"onset_time"``, or if *thresholds* is empty.

    Notes
    -----
    - All timestamps are converted to UTC before evaluation.
    - NaN signal values are dropped before any computation.
    - Input DataFrames are never mutated.
    - All outputs are deterministic.
    """
    # Validate thresholds first (mirrors PR 2 error message)
    thresholds_arr = np.asarray(thresholds, dtype=float).ravel()
    if thresholds_arr.size == 0:
        raise ValueError("thresholds must be a non-empty 1D array-like")

    # Validate flare_df
    if "onset_time" not in flare_df.columns:
        raise ValueError("flare_df must contain column: 'onset_time'")

    # Build the two-column signal DataFrame (validates feature_df columns)
    signal_df = _prepare_signal_df(feature_df, time_col, value_col)

    # --- Evaluation steps ---
    lead_times = compute_lead_times(signal_df, flare_df)
    threshold_metrics = compute_threshold_metrics(signal_df, flare_df, thresholds_arr)
    fpr_sorted, tpr_sorted, thresholds_sorted = compute_roc(
        signal_df, flare_df, thresholds_arr
    )
    auc_value = compute_auc(fpr_sorted, tpr_sorted) if fpr_sorted.size >= 2 else np.nan

    return {
        "lead_times": lead_times,
        "threshold_metrics": threshold_metrics,
        "roc_fpr": fpr_sorted,
        "roc_tpr": tpr_sorted,
        "roc_thresholds": thresholds_sorted,
        "auc": auc_value,
    }


# ---------------------------------------------------------------------------
# Public API: evaluate_precursor_window
# ---------------------------------------------------------------------------

def evaluate_precursor_window(
    *,
    feature_df: pd.DataFrame,
    flare_df: pd.DataFrame,
    time_col: str = "time",
    value_col: str = "delta_phi",
    pre_window_start_hours: float = 24,
    pre_window_end_hours: float = 6,
    thresholds: "np.ndarray | list[float]",
) -> "dict[str, pd.DataFrame | np.ndarray | float]":
    """Evaluate ΔΦ(t) within the 6–24 h precursor window before each flare.

    For each flare event the precursor window is defined as
    ``[onset − pre_window_start_hours, onset − pre_window_end_hours)``.
    A boolean precursor indicator records whether ΔΦ(t) exceeds each
    threshold inside this window.  Standard threshold metrics (TP, FP, TN,
    FN, TPR, FPR), ROC curve, AUC, and lead-time distribution are also
    computed via the existing event-based evaluation layer.

    Parameters
    ----------
    feature_df : pd.DataFrame
        Must contain *time_col* and *value_col*.
    flare_df : pd.DataFrame
        Must contain ``"onset_time"``.
    time_col : str, optional
        Name of the timestamp column in *feature_df*.  Default ``"time"``.
    value_col : str, optional
        Name of the signal column in *feature_df*.  Default ``"delta_phi"``.
    pre_window_start_hours : float, optional
        Hours before onset at which the precursor window opens.  Default 24.
    pre_window_end_hours : float, optional
        Hours before onset at which the precursor window closes.  Default 6.
    thresholds : array-like of float
        Non-empty 1D sequence of threshold values for the evaluation sweep.

    Returns
    -------
    dict with keys:
        ``"precursor_indicators"`` – :class:`pd.DataFrame` with columns
            ``onset_time`` and one bool column per threshold value (named
            ``"exceeds_<threshold>"``), recording whether ΔΦ(t) exceeded
            that threshold anywhere in the precursor window.
        ``"window_stats"`` – :class:`pd.DataFrame` with per-flare statistics
            in the precursor window: ``max_delta_phi``, ``mean_delta_phi``,
            ``n_samples``.
        ``"threshold_metrics"`` – :class:`pd.DataFrame` (one row per threshold)
        ``"roc_fpr"``          – :class:`np.ndarray`
        ``"roc_tpr"``          – :class:`np.ndarray`
        ``"roc_thresholds"``   – :class:`np.ndarray`
        ``"auc"``              – float
        ``"lead_times"``       – :class:`pd.DataFrame`

    Raises
    ------
    ValueError
        If required columns are missing, *flare_df* lacks ``"onset_time"``,
        or *thresholds* is empty.

    Notes
    -----
    - ``pre_window_start_hours`` must be strictly greater than
      ``pre_window_end_hours``.
    - The threshold_metrics / ROC / AUC outputs use the full
      ``pre_window_start_hours``-wide window (matching ``evaluate_precursor``
      semantics), while ``precursor_indicators`` and ``window_stats`` use the
      narrower ``[onset − start, onset − end)`` window.
    - All timestamps are converted to UTC before evaluation.

    References
    ----------
    PAPER.md §12.3 — ΔΦ(t) behaviour prior to flares.
    PAPER.md §12.4 — forecasting metrics.
    """
    # --- Validate inputs ---
    thresholds_arr = np.asarray(thresholds, dtype=float).ravel()
    if thresholds_arr.size == 0:
        raise ValueError("thresholds must be a non-empty 1D array-like")
    if "onset_time" not in flare_df.columns:
        raise ValueError("flare_df must contain column: 'onset_time'")

    # Build the two-column signal DataFrame (validates feature_df columns)
    signal_df = _prepare_signal_df(feature_df, time_col, value_col)

    flares = flare_df[["onset_time"]].copy()
    flares["onset_time"] = pd.to_datetime(flares["onset_time"], utc=True)

    W_start = pd.Timedelta(hours=pre_window_start_hours)
    W_end   = pd.Timedelta(hours=pre_window_end_hours)

    # --- Per-flare precursor-window extraction ---
    indicator_rows: list[dict] = []
    stats_rows: list[dict] = []

    for onset in flares["onset_time"]:
        win_start = onset - W_start
        win_end   = onset - W_end
        mask = (signal_df["time"] >= win_start) & (signal_df["time"] < win_end)
        window = signal_df.loc[mask, "signal"].dropna().to_numpy()

        stats_row: dict = {
            "onset_time":     onset,
            "max_delta_phi":  float(np.max(window))  if window.size > 0 else np.nan,
            "mean_delta_phi": float(np.mean(window)) if window.size > 0 else np.nan,
            "n_samples":      int(window.size),
        }
        stats_rows.append(stats_row)

        ind_row: dict = {"onset_time": onset}
        for theta in thresholds_arr:
            ind_row[f"exceeds_{theta:.3f}"] = bool(
                window.size > 0 and np.any(window >= theta)
            )
        indicator_rows.append(ind_row)

    indicator_df = (
        pd.DataFrame(indicator_rows)
        if indicator_rows
        else pd.DataFrame(
            columns=["onset_time"]
            + [f"exceeds_{t:.3f}" for t in thresholds_arr]
        )
    )
    stats_df = (
        pd.DataFrame(stats_rows)
        if stats_rows
        else pd.DataFrame(
            columns=["onset_time", "max_delta_phi", "mean_delta_phi", "n_samples"]
        )
    )

    # --- Standard event-based metrics (full pre_window_start_hours window) ---
    threshold_metrics = compute_threshold_metrics(signal_df, flare_df, thresholds_arr)
    fpr_sorted, tpr_sorted, thresholds_sorted = compute_roc(
        signal_df, flare_df, thresholds_arr
    )
    auc_value = (
        compute_auc(fpr_sorted, tpr_sorted) if fpr_sorted.size >= 2 else np.nan
    )
    lead_times = compute_lead_times(signal_df, flare_df)

    return {
        "precursor_indicators": indicator_df,
        "window_stats":         stats_df,
        "threshold_metrics":    threshold_metrics,
        "roc_fpr":              fpr_sorted,
        "roc_tpr":              tpr_sorted,
        "roc_thresholds":       thresholds_sorted,
        "auc":                  auc_value,
        "lead_times":           lead_times,
    }
