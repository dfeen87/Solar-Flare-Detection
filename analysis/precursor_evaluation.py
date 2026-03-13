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
