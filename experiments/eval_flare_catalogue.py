"""
experiments/eval_flare_catalogue.py
====================================
Evaluate the ΔΦ(t) precursor operator against the NOAA flare catalogue.

Reads ``noaa_goes18_xrs_1m.csv.zip`` from the repository root, derives the
ΔΦ(t) time series from the GOES-18 long-wave X-ray channel, and evaluates
the precursor signal against flare event times using the 6–24 h precursor
window defined in §12.2 of ANALYSIS_AND_VALIDATION.md.

When no external catalogue is supplied via ``--catalogue``, flare-like events
are detected automatically as local maxima in the smoothed XRS flux that
exceed the C-class threshold (1×10⁻⁶ W m⁻²).

Steps
-----
1. Read ``noaa_goes18_xrs_1m.csv.zip`` (repository root).
2. Convert J2000 epoch seconds → UTC timestamps.
3. Compute ΔΦ(t) = Φ(t) − Φ(t − Δt) from the normalised long-wave flux.
4. Load an external NOAA flare catalogue if ``--catalogue`` is given;
   otherwise derive flare-like events from XRS local maxima
   (``shared.data_loader.load_noaa_flare_catalogue`` or peak detection).
5. Align flare onset times with the ΔΦ(t) timeline via
   ``shared.event_evaluation.align_flare_onsets``.
6. Evaluate ΔΦ(t) in the 6–24 h precursor window per flare via
   ``analysis.precursor_evaluation.evaluate_precursor_window``.
7. Compute ROC curve, AUC, lead-time distribution, false-alarm and
   missed-event rates.
8. Save JSON metrics to ``results/flare_catalogue_eval.json`` and plots to
   ``results/``.

Usage
-----
::

    python experiments/eval_flare_catalogue.py
    python experiments/eval_flare_catalogue.py --catalogue /path/to/flares.csv
    python experiments/eval_flare_catalogue.py --months 3

Options
-------
--catalogue PATH
    Path to a NOAA flare catalogue CSV or JSON file.  If omitted, flare
    events are detected from the XRS time series.
--months N
    Number of months of GOES-18 data to analyse (default: 1).
--threshold-lo FLOAT
    Lower bound of the threshold sweep (default: 0.1).
--threshold-hi FLOAT
    Upper bound of the threshold sweep (default: 0.9).
--n-thresholds INT
    Number of thresholds in the sweep (default: 50).
--output PATH
    Output JSON file (default: results/flare_catalogue_eval.json).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # non-interactive backend, no display required
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Allow importing shared/ and analysis/ regardless of working directory.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from analysis.precursor_evaluation import evaluate_precursor_window  # noqa: E402
from shared.data_loader import load_noaa_flare_catalogue             # noqa: E402
from shared.event_evaluation import align_flare_onsets              # noqa: E402
from shared.precursor_features import compute_delta_phi             # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_ZIP        = _REPO_ROOT / "noaa_goes18_xrs_1m.csv.zip"
_DEFAULT_OUTPUT     = _REPO_ROOT / "results" / "flare_catalogue_eval.json"
_J2000              = datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
_T0                 = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

# C-class flux threshold (W m⁻²) used for automatic flare detection
_CCLASS_THRESHOLD   = 1e-6
# Minimum time between detected flare events
_MIN_FLARE_SEP_HRS  = 2.0
# Rolling smoothing window for peak detection (samples = minutes)
_SMOOTH_WINDOW      = 10


# ---------------------------------------------------------------------------
# Internal: load XRS data from ZIP
# ---------------------------------------------------------------------------

def _load_xrs_slice(
    zip_path: Path,
    start_dt: datetime,
    end_dt: datetime,
) -> pd.DataFrame:
    """Load and return the GOES-18 XRS long-wave channel for [start_dt, end_dt).

    Returns
    -------
    pd.DataFrame
        Columns: ``time`` (UTC-aware), ``xrs_long`` (float, W m⁻²).
    """
    with zipfile.ZipFile(zip_path, "r") as zf:
        csv_names = [n for n in zf.namelist()
                     if not n.startswith("__MACOSX") and n.endswith(".csv")]
        if not csv_names:
            raise FileNotFoundError(f"No CSV file found inside {zip_path}")
        with zf.open(csv_names[0]) as fh:
            raw = pd.read_csv(fh)

    raw.columns = [c.strip() for c in raw.columns]

    col_time = "time (seconds since 2000-01-01 12:00:00)"
    col_lw   = "longwave_masked (W/m^2)"

    epoch_ns = int(_J2000.timestamp() * 1e9)
    timestamps = pd.to_datetime(
        epoch_ns + (raw[col_time].astype(float) * 1e9).astype("int64"),
        utc=True,
    )

    df = pd.DataFrame({
        "time":     timestamps,
        "xrs_long": raw[col_lw].astype(float),
    })

    # Replace fill values (negative flux) with NaN
    df.loc[df["xrs_long"] <= 0, "xrs_long"] = np.nan

    # Filter to requested interval
    df = df[(df["time"] >= start_dt) & (df["time"] < end_dt)].copy()
    df = df.dropna(subset=["xrs_long"])
    df = df.sort_values("time").reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# Internal: derive ΔΦ(t) from XRS flux
# ---------------------------------------------------------------------------

def _compute_delta_phi_from_xrs(
    xrs_df: pd.DataFrame,
    delta_hours: float = 1.0,
) -> pd.DataFrame:
    """Compute ΔΦ(t) from the log10-normalised long-wave XRS flux.

    The log10-transformed, min-max normalised flux is used as the scalar
    Φ(t) time series; ΔΦ(t) is then computed as the backward difference
    Φ(t) − Φ(t − delta_hours).  Log-scale normalisation is used because
    solar X-ray flux spans several orders of magnitude; it ensures that
    both quiet-Sun and active periods contribute meaningfully to the signal.

    Returns
    -------
    pd.DataFrame
        Columns: ``time`` (UTC-aware), ``phi`` (float), ``delta_phi`` (float).
    """
    flux = xrs_df["xrs_long"].to_numpy(dtype=float)

    # Take log10 (flux values are positive after fill-value removal)
    log_flux = np.log10(np.maximum(flux, 1e-10))

    # Min-max normalise to [0, 1] (NaN-safe)
    lo = np.nanmin(log_flux)
    hi = np.nanmax(log_flux)
    if hi > lo:
        phi_vals = (log_flux - lo) / (hi - lo)
    else:
        phi_vals = np.zeros_like(log_flux)

    phi_df = pd.DataFrame({
        "time": xrs_df["time"].values,
        "phi":  phi_vals,
    })

    return compute_delta_phi(phi_df, delta=pd.Timedelta(hours=delta_hours))


# ---------------------------------------------------------------------------
# Internal: automatic flare detection from XRS peaks
# ---------------------------------------------------------------------------

def _detect_flares_from_xrs(
    xrs_df: pd.DataFrame,
    flux_threshold: float = _CCLASS_THRESHOLD,
    min_separation_hours: float = _MIN_FLARE_SEP_HRS,
) -> pd.DataFrame:
    """Detect flare-like events as local maxima in the XRS long-wave flux.

    Parameters
    ----------
    xrs_df : pd.DataFrame
        Columns: ``time`` (UTC-aware), ``xrs_long`` (float, W m⁻²).
    flux_threshold : float
        Minimum flux for a peak to qualify as a flare-like event.
    min_separation_hours : float
        Minimum time between consecutive flare events.

    Returns
    -------
    pd.DataFrame
        Columns: ``onset_time``, ``time_begin``, ``time_max``, ``time_end``,
        ``class_type``, ``class_num``.
    """
    flux  = xrs_df["xrs_long"].to_numpy(dtype=float)
    times = xrs_df["time"].to_numpy(dtype="datetime64[ns]")


    # Rolling median smoothing to suppress 1–2 sample noise spikes
    flux_smooth = (
        pd.Series(flux)
        .rolling(_SMOOTH_WINDOW, center=True, min_periods=1)
        .median()
        .to_numpy()
    )

    # Find local maxima above threshold
    n = len(flux_smooth)
    candidates: list[int] = []
    for i in range(1, n - 1):
        if (
            flux_smooth[i] > flux_smooth[i - 1]
            and flux_smooth[i] > flux_smooth[i + 1]
            and flux_smooth[i] >= flux_threshold
        ):
            candidates.append(i)

    if not candidates:
        return pd.DataFrame(columns=[
            "onset_time", "time_begin", "time_max", "time_end",
            "class_type", "class_num",
        ])

    # Apply minimum-separation filter: keep peaks with sufficient gap,
    # replacing earlier peak when a taller neighbour is closer than min_sep.
    min_sep_ns = int(min_separation_hours * 3600 * 1e9)
    selected: list[int] = [candidates[0]]
    for idx in candidates[1:]:
        prev = selected[-1]
        gap = int(times[idx]) - int(times[prev])
        if gap >= min_sep_ns:
            selected.append(idx)
        elif flux_smooth[idx] > flux_smooth[prev]:
            # Replace the previous peak with the taller one
            selected[-1] = idx

    # Build flare catalogue from selected peaks
    rows: list[dict] = []
    for idx in selected:
        f = flux_smooth[idx]
        if f >= 1e-4:
            cls, num = "X", f / 1e-4
        elif f >= 1e-5:
            cls, num = "M", f / 1e-5
        elif f >= 1e-6:
            cls, num = "C", f / 1e-6
        else:
            cls, num = "B", f / 1e-7
        onset = pd.Timestamp(times[idx])
        rows.append({
            "onset_time": onset,
            "time_begin": onset,
            "time_max":   onset,
            "time_end":   onset + pd.Timedelta(minutes=30),
            "class_type": cls,
            "class_num":  round(num, 1),
        })

    df = pd.DataFrame(rows)
    df = df.sort_values("onset_time").reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# Internal: JSON serialisation helpers
# ---------------------------------------------------------------------------

def _float_or_none(value) -> "float | None":
    """Return *value* as a Python float, or None if NaN / non-finite."""
    try:
        f = float(value)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _ts_or_none(value) -> "str | None":
    """Return an ISO-8601 UTC string, or None for NaT / None."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    try:
        ts = pd.Timestamp(value)
        if ts is pd.NaT:
            return None
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        return ts.isoformat()
    except Exception:
        return None


def _df_to_records(df: pd.DataFrame) -> list[dict]:
    """Convert a DataFrame to a list of JSON-serialisable dicts."""
    records = []
    for row in df.itertuples(index=False):
        d: dict = {}
        for col, val in zip(df.columns, row):
            if isinstance(val, (pd.Timestamp,)) or hasattr(val, "isoformat"):
                d[col] = _ts_or_none(val)
            elif isinstance(val, (bool, np.bool_)):
                d[col] = bool(val)
            elif isinstance(val, (int, np.integer)):
                d[col] = int(val)
            elif isinstance(val, (float, np.floating)):
                d[col] = _float_or_none(val)
            else:
                d[col] = val
        records.append(d)
    return records


# ---------------------------------------------------------------------------
# Internal: plotting
# ---------------------------------------------------------------------------

def _save_roc_plot(fpr, tpr, auc_value: float, output_dir: Path) -> Path:
    """Save ROC curve to *output_dir*/flare_catalogue_roc.png."""
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.plot(fpr, tpr, color="#2980b9", lw=2,
            label=f"ΔΦ(t)  (AUC = {auc_value:.3f})")
    ax.plot([0, 1], [0, 1], "k--", lw=1, label="Random")
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.set_title("ROC — ΔΦ(t) Flare Precursor")
    ax.legend(loc="lower right")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    fig.tight_layout()
    out = output_dir / "flare_catalogue_roc.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def _save_lead_time_plot(lead_times_df: pd.DataFrame, output_dir: Path) -> Path:
    """Save lead-time distribution histogram to *output_dir*."""
    lt = lead_times_df["lead_time_first_crossing_hours"].dropna().to_numpy()
    fig, ax = plt.subplots(figsize=(6, 4))
    if lt.size > 0:
        ax.hist(lt, bins=min(20, lt.size), color="#e67e22", edgecolor="white")
        ax.set_xlabel("Lead time (hours)")
        ax.set_ylabel("Count")
        ax.set_title("Lead-Time Distribution — ΔΦ(t) First Threshold Crossing")
    else:
        ax.text(0.5, 0.5, "No crossings detected",
                ha="center", va="center", transform=ax.transAxes)
        ax.set_title("Lead-Time Distribution")
    fig.tight_layout()
    out = output_dir / "flare_catalogue_lead_times.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def _save_delta_phi_plot(
    delta_phi_df: pd.DataFrame,
    flare_df: pd.DataFrame,
    output_dir: Path,
) -> Path:
    """Save ΔΦ(t) timeline with flare-onset markers."""
    fig, ax = plt.subplots(figsize=(10, 3))
    ax.plot(delta_phi_df["time"], delta_phi_df["delta_phi"],
            color="#2c3e50", lw=0.6, label="ΔΦ(t)")
    for _, row in flare_df.iterrows():
        ax.axvline(row["onset_time"], color="#e74c3c", lw=0.8, alpha=0.6)
    ax.set_xlabel("Time (UTC)")
    ax.set_ylabel("ΔΦ(t)")
    ax.set_title("ΔΦ(t) with Flare Onsets")
    ax.legend(loc="upper right")
    fig.tight_layout()
    out = output_dir / "flare_catalogue_delta_phi.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# Main evaluation function
# ---------------------------------------------------------------------------

def run_flare_catalogue_eval(
    *,
    zip_path: Path = _DEFAULT_ZIP,
    catalogue_path: "Path | None" = None,
    months: int = 1,
    threshold_lo: float = 0.01,
    threshold_hi: float = 0.9,
    n_thresholds: int = 50,
    output: Path = _DEFAULT_OUTPUT,
) -> dict:
    """Run the full flare-catalogue precursor evaluation pipeline.

    Parameters
    ----------
    zip_path : Path
        Path to ``noaa_goes18_xrs_1m.csv.zip``.
    catalogue_path : Path or None
        Path to a NOAA flare catalogue CSV/JSON.  When None, events are
        detected automatically from the XRS time series.
    months : int
        Number of months of data to analyse starting from 2024-01-01.
    threshold_lo, threshold_hi : float
        Bounds of the ΔΦ threshold sweep (inclusive).
    n_thresholds : int
        Number of threshold values in the sweep.
    output : Path
        Path for the output JSON artefact.

    Returns
    -------
    dict
        The serialised evaluation results (also written to *output*).
    """
    start_dt = _T0
    end_dt   = _T0 + timedelta(days=30 * months)

    print(f"[eval_flare_catalogue] Interval: {start_dt.date()} — {end_dt.date()}")
    print(f"[eval_flare_catalogue] Loading XRS data from {zip_path.name} …")

    # 1. Load XRS data
    xrs_df = _load_xrs_slice(zip_path, start_dt, end_dt)
    print(f"[eval_flare_catalogue] Loaded {len(xrs_df):,} rows")

    # 2. Compute ΔΦ(t)
    print("[eval_flare_catalogue] Computing ΔΦ(t) …")
    delta_phi_df = _compute_delta_phi_from_xrs(xrs_df)

    # 3. Build feature DataFrame: use |ΔΦ(t)| as the precursor signal so that
    #    both rising and falling flux contribute equally to the metric.
    feature_df = delta_phi_df.copy()
    feature_df["delta_phi"] = feature_df["delta_phi"].abs()

    # 4. Load or detect flare catalogue
    if catalogue_path is not None:
        print(f"[eval_flare_catalogue] Loading flare catalogue from {catalogue_path} …")
        flare_df = load_noaa_flare_catalogue(
            catalogue_path,
            start=start_dt,
            end=end_dt,
        )
        print(f"[eval_flare_catalogue] Catalogue contains {len(flare_df)} events")
    else:
        print("[eval_flare_catalogue] No catalogue provided — detecting flares from XRS peaks …")
        flare_df = _detect_flares_from_xrs(xrs_df)
        print(f"[eval_flare_catalogue] Detected {len(flare_df)} flare-like events")

    if flare_df.empty:
        print("[eval_flare_catalogue] WARNING: no flare events found; metrics will be empty")

    # 5. Align flare onsets with ΔΦ(t) timeline
    print("[eval_flare_catalogue] Aligning flare onsets with ΔΦ(t) timeline …")
    aligned_df = align_flare_onsets(flare_df, delta_phi_df)

    # 6. Evaluate ΔΦ(t) in the 6–24 h precursor window
    thresholds = np.linspace(threshold_lo, threshold_hi, n_thresholds)
    print(
        f"[eval_flare_catalogue] Running precursor-window evaluation "
        f"(window: 6–24 h before onset, {n_thresholds} thresholds) …"
    )
    results = evaluate_precursor_window(
        feature_df=feature_df,
        flare_df=flare_df,
        value_col="delta_phi",
        pre_window_start_hours=24,
        pre_window_end_hours=6,
        thresholds=thresholds,
    )

    auc_value = results["auc"]
    print(f"[eval_flare_catalogue] AUC = {auc_value:.4f}")

    # 7. Compute summary false-alarm / missed-event rates at mid threshold
    mid_idx = n_thresholds // 2
    tm = results["threshold_metrics"]
    if not tm.empty:
        mid_row = tm.iloc[mid_idx]
        far   = float(mid_row["FPR"]) if not math.isnan(float(mid_row["FPR"])) else None
        mer   = float(mid_row["FNR"]) if not math.isnan(float(mid_row["FNR"])) else None
        mid_theta = float(mid_row["threshold"])
        print(
            f"[eval_flare_catalogue] At θ={mid_theta:.2f}: "
            f"FAR={far}, MER={mer}"
        )
    else:
        far, mer, mid_theta = None, None, None

    # 8. Save plots
    results_dir = output.parent
    results_dir.mkdir(parents=True, exist_ok=True)

    fpr = results["roc_fpr"]
    tpr = results["roc_tpr"]
    if fpr.size >= 2 and not math.isnan(auc_value):
        _save_roc_plot(fpr, tpr, auc_value, results_dir)
        print(f"[eval_flare_catalogue] ROC plot → {results_dir}/flare_catalogue_roc.png")

    _save_lead_time_plot(results["lead_times"], results_dir)
    print(
        f"[eval_flare_catalogue] Lead-time plot → "
        f"{results_dir}/flare_catalogue_lead_times.png"
    )

    _save_delta_phi_plot(delta_phi_df, flare_df, results_dir)
    print(
        f"[eval_flare_catalogue] ΔΦ(t) plot → "
        f"{results_dir}/flare_catalogue_delta_phi.png"
    )

    # 9. Build output JSON
    lead_times_df = results["lead_times"]
    valid_lt = (
        lead_times_df["lead_time_first_crossing_hours"]
        .dropna()
        .to_numpy()
        .tolist()
    )
    lt_mean = float(np.mean(valid_lt)) if valid_lt else None
    lt_median = float(np.median(valid_lt)) if valid_lt else None

    n_flares     = len(flare_df)
    n_with_lt    = int(np.sum(~lead_times_df["lead_time_first_crossing_hours"].isna()))
    n_detected   = int(
        results["threshold_metrics"]["TP"].iloc[mid_idx]
    ) if not tm.empty else 0
    n_missed     = int(
        results["threshold_metrics"]["FN"].iloc[mid_idx]
    ) if not tm.empty else n_flares

    output_dict = {
        "interval": {
            "start": start_dt.isoformat(),
            "end":   end_dt.isoformat(),
        },
        "n_flares": n_flares,
        "catalogue_source": (
            str(catalogue_path) if catalogue_path else "auto-detected from XRS peaks"
        ),
        "precursor_window_hours": {
            "start": 24,
            "end":   6,
        },
        "auc": _float_or_none(auc_value),
        "threshold_at_mid": _float_or_none(mid_theta),
        "false_alarm_rate":  _float_or_none(far),
        "missed_event_rate": _float_or_none(mer),
        "lead_time_hours": {
            "mean":   lt_mean,
            "median": lt_median,
            "values": [_float_or_none(v) for v in valid_lt],
        },
        "n_flares_with_lead_time": n_with_lt,
        "n_detected":  n_detected,
        "n_missed":    n_missed,
        "roc": {
            "fpr": [_float_or_none(v) for v in fpr.tolist()],
            "tpr": [_float_or_none(v) for v in tpr.tolist()],
            "thresholds": [
                _float_or_none(v)
                for v in results["roc_thresholds"].tolist()
            ],
        },
        "threshold_metrics": _df_to_records(results["threshold_metrics"]),
        "aligned_onsets": _df_to_records(aligned_df),
        "flare_events": _df_to_records(flare_df),
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as fh:
        json.dump(output_dict, fh, indent=2, default=str)
    print(f"[eval_flare_catalogue] Results → {output}")

    return output_dict


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main(argv: "list[str] | None" = None) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate ΔΦ(t) precursor operator against the NOAA flare catalogue "
            "using the GOES-18 XRS 1-minute dataset."
        ),
    )
    parser.add_argument(
        "--catalogue",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "Path to a NOAA flare catalogue CSV or JSON file.  "
            "If omitted, flares are detected from XRS peaks."
        ),
    )
    parser.add_argument(
        "--months",
        type=int,
        default=1,
        metavar="N",
        help="Number of months of GOES-18 data to analyse (default: 1).",
    )
    parser.add_argument(
        "--threshold-lo",
        type=float,
        default=0.01,
        metavar="FLOAT",
        help="Lower bound of the threshold sweep (default: 0.01).",
    )
    parser.add_argument(
        "--threshold-hi",
        type=float,
        default=0.9,
        metavar="FLOAT",
        help="Upper bound of the threshold sweep (default: 0.9).",
    )
    parser.add_argument(
        "--n-thresholds",
        type=int,
        default=50,
        metavar="INT",
        help="Number of thresholds in the sweep (default: 50).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_DEFAULT_OUTPUT,
        metavar="PATH",
        help="Output JSON file (default: results/flare_catalogue_eval.json).",
    )
    args = parser.parse_args(argv)

    run_flare_catalogue_eval(
        catalogue_path=args.catalogue,
        months=args.months,
        threshold_lo=args.threshold_lo,
        threshold_hi=args.threshold_hi,
        n_thresholds=args.n_thresholds,
        output=args.output,
    )


if __name__ == "__main__":
    main()
