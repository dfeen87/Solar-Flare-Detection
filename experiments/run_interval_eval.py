"""
experiments/run_interval_eval.py
=================================
Parametric evaluation script for any fixed date interval.

Runs the full precursor evaluation pipeline over a user-specified time range:

    1. Ingest GOES X-ray, magnetometer, EUV, and flare catalogue data.
    2. Compute ΔΦ(t) from the magnetometer He-component.
    3. Assemble composite features (ΔΦ, X-ray background, EUV).
    4. Run ``evaluate_precursor`` over a threshold sweep.
    5. Run ``run_shuffle_test`` to generate the null distribution.
    6. Persist structured results as a JSON artifact.

Command-line usage
------------------
::

    python experiments/run_interval_eval.py \\
        --start 2024-01-01 \\
        --end   2024-02-01 \\
        --value-col delta_phi \\
        --n-shuffles 200 \\
        --random-state 42 \\
        --output results/eval_2024-01-01_to_2024-02-01.json

Output structure
----------------
The saved JSON file contains::

    {
      "interval": {"start": "...", "end": "..."},
      "value_col": "...",
      "real_auc": float,
      "shuffle_aucs": [...],
      "p_value": float,
      "lead_times": [...],
      "threshold_metrics": [...],
      "roc": {"fpr": [...], "tpr": [...], "thresholds": [...]}
    }

Notes
-----
- All timestamps in the output are ISO-8601 UTC strings.
- NaN values in numeric fields are serialised as ``null``.
- The script is fully deterministic when ``--random-state`` is set.
- No plots are produced; only structured data artifacts are written.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Allow importing shared/ and analysis/ regardless of the working directory.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from analysis.precursor_evaluation import evaluate_precursor  # noqa: E402
from analysis.shuffle_test import run_shuffle_test  # noqa: E402
from shared.composite_features import assemble_precursor_features  # noqa: E402
from shared.data_loader import (  # noqa: E402
    load_flare_catalogue_range,
    load_goes_euv_range,
    load_goes_magnetometer_range,
    load_goes_xray_range,
)
from shared.precursor_features import compute_delta_phi  # noqa: E402


# ---------------------------------------------------------------------------
# JSON serialisation helpers
# ---------------------------------------------------------------------------

def _float_or_none(value) -> "float | None":
    """Return *value* as a Python float, or None if it is NaN / non-finite."""
    try:
        f = float(value)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _series_to_list(series: pd.Series) -> list:
    """Convert a pandas Series to a JSON-serialisable list.

    Timestamps are rendered as ISO-8601 UTC strings; NaN floats become None.
    """
    out = []
    for v in series:
        if isinstance(v, pd.Timestamp):
            out.append(v.isoformat() if not pd.isnull(v) else None)
        elif isinstance(v, float):
            out.append(_float_or_none(v))
        else:
            out.append(v)
    return out


def _df_to_records(df: pd.DataFrame) -> list[dict]:
    """Serialise a DataFrame to a list of dicts suitable for JSON output."""
    records = []
    for _, row in df.iterrows():
        record: dict = {}
        for col in df.columns:
            v = row[col]
            if isinstance(v, pd.Timestamp):
                record[col] = v.isoformat() if not pd.isnull(v) else None
            elif isinstance(v, float):
                record[col] = _float_or_none(v)
            elif isinstance(v, np.floating):
                record[col] = _float_or_none(float(v))
            elif isinstance(v, np.integer):
                record[col] = int(v)
            else:
                record[col] = v
        records.append(record)
    return records


def _ndarray_to_list(arr: np.ndarray) -> list:
    """Convert a 1-D numpy array to a JSON-serialisable list."""
    return [_float_or_none(float(v)) for v in arr]


# ---------------------------------------------------------------------------
# Data ingestion
# ---------------------------------------------------------------------------

def _load_interval_data(
    start: str,
    end: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load all required GOES data for the given [start, end) interval.

    Parameters
    ----------
    start, end:
        ISO date strings (YYYY-MM-DD).

    Returns
    -------
    tuple of (xray_df, magnetometer_df, euv_df, flare_df)
    """
    xray_df = load_goes_xray_range(start, end, include_background=True)
    magnetometer_df = load_goes_magnetometer_range(start, end)
    euv_df = load_goes_euv_range(start, end)
    flare_df = load_flare_catalogue_range(start, end)
    return xray_df, magnetometer_df, euv_df, flare_df


# ---------------------------------------------------------------------------
# Precursor feature construction
# ---------------------------------------------------------------------------

def _build_feature_df(
    magnetometer_df: pd.DataFrame,
    xray_df: pd.DataFrame,
    euv_df: pd.DataFrame,
) -> pd.DataFrame:
    """Compute ΔΦ(t) and assemble the composite feature table.

    Parameters
    ----------
    magnetometer_df:
        DataFrame with ``time`` and ``He`` columns.
    xray_df:
        DataFrame with ``time`` and ``background_flux`` columns.
    euv_df:
        DataFrame with ``time`` and at least one EUV channel column.

    Returns
    -------
    pd.DataFrame
        Composite feature table with columns
        ``["time", "delta_phi", "xray", "euv"]``.
    """
    # ΔΦ(t) — backward finite difference of He(t)
    delta_phi_df = compute_delta_phi(
        magnetometer_df,
        time_col="time",
        value_col="He",
    )
    # delta_phi_df has columns: time, phi, delta_phi

    # X-ray background column.  `load_goes_xray_range(include_background=True)`
    # returns both `flux` and `background_flux`; fall back to `flux` if the
    # background column is absent (e.g. when the SWPC endpoint returns no data).
    if "background_flux" in xray_df.columns:
        xray_col = "background_flux"
    elif "flux" in xray_df.columns:
        xray_col = "flux"
    else:
        raise ValueError(
            "xray_df must contain either 'background_flux' or 'flux' column"
        )

    # EUV: use the first non-time channel found
    euv_channels = [c for c in euv_df.columns if c != "time"]
    if not euv_channels:
        # No EUV channels: create a placeholder column of NaNs
        euv_df = euv_df.copy()
        euv_df["euv"] = np.nan
        euv_col = "euv"
    else:
        euv_col = euv_channels[0]

    feature_df = assemble_precursor_features(
        delta_phi_df=delta_phi_df,
        xray_df=xray_df,
        euv_df=euv_df,
        time_col="time",
        delta_phi_col="delta_phi",
        xray_col=xray_col,
        euv_col=euv_col,
    )
    return feature_df


# ---------------------------------------------------------------------------
# Flare DataFrame normalisation
# ---------------------------------------------------------------------------

def _prepare_flare_df(flare_df: pd.DataFrame) -> pd.DataFrame:
    """Return a flare DataFrame with an ``onset_time`` column.

    ``evaluate_precursor`` and ``run_shuffle_test`` require an ``onset_time``
    column; the catalogue loader returns ``time_begin`` instead.
    """
    df = flare_df.copy()
    if "onset_time" not in df.columns:
        df["onset_time"] = df["time_begin"]
    return df


# ---------------------------------------------------------------------------
# Threshold generation
# ---------------------------------------------------------------------------

def _build_thresholds(feature_df: pd.DataFrame, value_col: str) -> np.ndarray:
    """Build a default threshold sweep from signal percentiles.

    Generates 50 evenly-spaced thresholds spanning the 5th–95th percentile
    of the non-NaN signal values.  This avoids boundary artefacts from
    extremes while covering the bulk of the distribution.
    """
    signal = feature_df[value_col].dropna().to_numpy()
    if signal.size == 0:
        return np.array([0.0])
    lo = float(np.percentile(signal, 5))
    hi = float(np.percentile(signal, 95))
    if lo == hi:
        return np.array([lo])
    return np.linspace(lo, hi, 50)


# ---------------------------------------------------------------------------
# Result serialisation
# ---------------------------------------------------------------------------

def _build_result(
    start: str,
    end: str,
    value_col: str,
    eval_result: dict,
    shuffle_result: dict,
) -> dict:
    """Combine evaluation and shuffle results into the output structure."""
    return {
        "interval": {"start": start, "end": end},
        "value_col": value_col,
        "real_auc": _float_or_none(shuffle_result["real_auc"]),
        "shuffle_aucs": _ndarray_to_list(shuffle_result["shuffle_aucs"]),
        "p_value": _float_or_none(shuffle_result["p_value"]),
        "lead_times": _df_to_records(eval_result["lead_times"]),
        "threshold_metrics": _df_to_records(eval_result["threshold_metrics"]),
        "roc": {
            "fpr": _ndarray_to_list(eval_result["roc_fpr"]),
            "tpr": _ndarray_to_list(eval_result["roc_tpr"]),
            "thresholds": _ndarray_to_list(eval_result["roc_thresholds"]),
        },
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_interval_eval(
    start: str,
    end: str,
    *,
    value_col: str = "delta_phi",
    n_shuffles: int = 200,
    random_state: "int | None" = None,
    output: "str | Path | None" = None,
) -> dict:
    """Run the full precursor evaluation pipeline over [start, end).

    Parameters
    ----------
    start, end:
        ISO date strings (YYYY-MM-DD) defining the half-open interval.
    value_col:
        Name of the feature column to evaluate.  Must be present in the
        assembled feature table.  Default is ``"delta_phi"``.
    n_shuffles:
        Number of shuffle-test permutations.  Default is ``200``.
    random_state:
        RNG seed for reproducibility.  Pass ``None`` for non-deterministic
        behaviour.
    output:
        Path to write the JSON result artifact.  If ``None``, the result is
        returned but not written to disk.

    Returns
    -------
    dict
        Structured results dictionary (see module docstring for schema).
    """
    print(f"[run_interval_eval] Loading GOES data for [{start}, {end}) …")
    xray_df, magnetometer_df, euv_df, flare_df = _load_interval_data(start, end)

    print("[run_interval_eval] Building composite feature table …")
    feature_df = _build_feature_df(magnetometer_df, xray_df, euv_df)

    flare_df_eval = _prepare_flare_df(flare_df)

    thresholds = _build_thresholds(feature_df, value_col)

    print(
        f"[run_interval_eval] Running evaluate_precursor "
        f"(value_col={value_col!r}, {len(thresholds)} thresholds) …"
    )
    eval_result = evaluate_precursor(
        feature_df=feature_df,
        flare_df=flare_df_eval,
        value_col=value_col,
        thresholds=thresholds,
    )

    print(
        f"[run_interval_eval] Running shuffle test "
        f"(n_shuffles={n_shuffles}, random_state={random_state}) …"
    )
    shuffle_result = run_shuffle_test(
        feature_df=feature_df,
        flare_df=flare_df_eval,
        value_col=value_col,
        thresholds=thresholds,
        n_shuffles=n_shuffles,
        random_state=random_state,
    )

    result = _build_result(start, end, value_col, eval_result, shuffle_result)

    if output is not None:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)
        print(f"[run_interval_eval] Results written to {output_path}")

    return result


def _parse_args(argv: "list[str] | None" = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the full precursor evaluation pipeline over a fixed date interval."
        ),
    )
    parser.add_argument(
        "--start",
        required=True,
        metavar="YYYY-MM-DD",
        help="Interval start date (inclusive).",
    )
    parser.add_argument(
        "--end",
        required=True,
        metavar="YYYY-MM-DD",
        help="Interval end date (exclusive).",
    )
    parser.add_argument(
        "--value-col",
        default="delta_phi",
        metavar="FEATURE",
        help="Feature column to evaluate (default: delta_phi).",
    )
    parser.add_argument(
        "--n-shuffles",
        type=int,
        default=200,
        metavar="N",
        help="Number of shuffle-test permutations (default: 200).",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=None,
        metavar="SEED",
        help="RNG seed for reproducibility (default: None).",
    )
    parser.add_argument(
        "--output",
        default=None,
        metavar="PATH",
        help="Path for the JSON output artifact.",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = _parse_args()
    run_interval_eval(
        start=args.start,
        end=args.end,
        value_col=args.value_col,
        n_shuffles=args.n_shuffles,
        random_state=args.random_state,
        output=args.output,
    )
