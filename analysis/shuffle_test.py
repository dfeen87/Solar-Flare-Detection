"""
shuffle_test — Shuffle-test (null model) for statistical falsification of
precursor signals.

Public API
----------
run_shuffle_test(
    *,
    feature_df,
    flare_df,
    time_col="time",
    value_col="delta_phi",
    thresholds,
    n_shuffles=200,
    random_state=None,
) -> dict[str, pd.DataFrame | np.ndarray | float]

Mathematical definitions
------------------------
Let S(tᵢ) be the precursor signal with timestamps tᵢ.

The shuffle test generates a null distribution by randomly permuting the
signal values (while preserving timestamps) n_shuffles times and recomputing
the AUC for each permuted signal.  The p-value is defined as the fraction of
shuffled AUC values that are greater than or equal to the real AUC:

    p = #{shuffled_AUC ≥ real_AUC} / n_shuffles

A small p-value (e.g. p < 0.05) indicates that the real precursor performs
better than chance.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from analysis.precursor_evaluation import evaluate_precursor


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_shuffle_test(
    *,
    feature_df: pd.DataFrame,
    flare_df: pd.DataFrame,
    time_col: str = "time",
    value_col: str = "delta_phi",
    thresholds: "np.ndarray | list[float]",
    n_shuffles: int = 200,
    random_state: "int | None" = None,
) -> "dict[str, np.ndarray | float]":
    """Run a deterministic shuffle test (null model) for a precursor signal.

    For each of *n_shuffles* iterations the signal values are randomly
    permuted (timestamps are preserved) and the AUC is recomputed.  The
    resulting distribution of shuffled AUC values serves as the null model
    against which the real AUC is compared.

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
        Non-empty 1D sequence of threshold values forwarded to
        :func:`~analysis.precursor_evaluation.evaluate_precursor`.
    n_shuffles : int, optional
        Number of random permutations.  Must be > 0.  Default ``200``.
    random_state : int or None, optional
        Seed for :func:`numpy.random.default_rng` to ensure reproducibility.
        Pass ``None`` for non-deterministic behaviour.

    Returns
    -------
    dict with keys:
        ``"real_auc"``    – float, AUC of the real (unshuffled) signal.
        ``"shuffle_aucs"`` – :class:`numpy.ndarray` of shape ``(n_shuffles,)``.
        ``"p_value"``     – float, fraction of shuffled AUC ≥ real AUC.

    Raises
    ------
    ValueError
        If *feature_df* is missing *time_col* or *value_col*, if *flare_df*
        is missing ``"onset_time"``, if *thresholds* is empty, if
        *n_shuffles* ≤ 0, or if the signal column contains only NaN values.

    Notes
    -----
    - All timestamps are converted to UTC before evaluation.
    - NaN signal values are dropped before shuffling.
    - Input DataFrames are never mutated.
    - Shuffling is fully reproducible when *random_state* is set.
    """
    # ------------------------------------------------------------------
    # Validate n_shuffles
    # ------------------------------------------------------------------
    if n_shuffles <= 0:
        raise ValueError("n_shuffles must be > 0")

    # ------------------------------------------------------------------
    # Validate required columns (mirrors evaluate_precursor error messages)
    # ------------------------------------------------------------------
    if time_col not in feature_df.columns:
        raise ValueError(
            f"feature_df must contain column: '{time_col}'"
        )
    if value_col not in feature_df.columns:
        raise ValueError(
            f"feature_df must contain column: '{value_col}'"
        )
    if "onset_time" not in flare_df.columns:
        raise ValueError("flare_df must contain column: 'onset_time'")

    # ------------------------------------------------------------------
    # Build a clean working copy (UTC, NaN-dropped, sorted) — no mutation
    # ------------------------------------------------------------------
    work_df = feature_df[[time_col, value_col]].copy()
    work_df[time_col] = pd.to_datetime(work_df[time_col], utc=True)
    work_df = work_df.dropna(subset=[value_col]).reset_index(drop=True)

    if work_df.empty:
        raise ValueError(
            f"feature_df signal column '{value_col}' contains only NaN values"
        )

    work_df = work_df.sort_values(time_col).reset_index(drop=True)

    # ------------------------------------------------------------------
    # Real AUC
    # ------------------------------------------------------------------
    real_result = evaluate_precursor(
        feature_df=work_df,
        flare_df=flare_df,
        time_col=time_col,
        value_col=value_col,
        thresholds=thresholds,
    )
    real_auc: float = real_result["auc"]

    # ------------------------------------------------------------------
    # Null distribution via random permutations
    # ------------------------------------------------------------------
    rng = np.random.default_rng(random_state)
    signal_values = work_df[value_col].to_numpy().copy()
    shuffle_aucs = np.empty(n_shuffles, dtype=float)

    for i in range(n_shuffles):
        permuted_values = rng.permutation(signal_values)
        shuffled_df = work_df.copy()
        shuffled_df[value_col] = permuted_values

        shuffled_result = evaluate_precursor(
            feature_df=shuffled_df,
            flare_df=flare_df,
            time_col=time_col,
            value_col=value_col,
            thresholds=thresholds,
        )
        shuffle_aucs[i] = shuffled_result["auc"]

    # ------------------------------------------------------------------
    # p-value: fraction of shuffled AUC >= real AUC
    # ------------------------------------------------------------------
    p_value: float = float(np.mean(shuffle_aucs >= real_auc))

    return {
        "real_auc": real_auc,
        "shuffle_aucs": shuffle_aucs,
        "p_value": p_value,
    }
