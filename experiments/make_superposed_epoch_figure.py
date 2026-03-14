"""
experiments/make_superposed_epoch_figure.py
============================================
Generate the superposed-epoch mean of |ΔΦ(t)| around flare onsets and save
the result to ``output/paper_figures/fig9_superposed_epoch.png``.

The script re-uses the same GOES-18 XRS 1-minute data and ΔΦ(t) pipeline
from ``eval_flare_catalogue`` and aligns ΔΦ(t) windows to every detected
flare onset to produce the ensemble-averaged precursor curve.

Usage
-----
::

    python experiments/make_superposed_epoch_figure.py
    python experiments/make_superposed_epoch_figure.py --months 3
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Allow importing shared/ and experiments/ regardless of working directory.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from experiments.eval_flare_catalogue import (       # noqa: E402
    _DEFAULT_ZIP,
    _load_xrs_slice,
    _compute_delta_phi_from_xrs,
    _detect_flares_from_xrs,
)
from shared.plot_utils import plot_superposed_epoch   # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_T0 = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
_OUTPUT_DIR = _REPO_ROOT / "output" / "paper_figures"


# ---------------------------------------------------------------------------
# Core: build the superposed-epoch matrix
# ---------------------------------------------------------------------------

def build_superposed_epoch_matrix(
    delta_phi_df: pd.DataFrame,
    flare_df: pd.DataFrame,
    pre_hours: float = 24.0,
    post_hours: float = 6.0,
) -> tuple[np.ndarray, np.ndarray, int]:
    """Align |ΔΦ(t)| windows to flare onsets and stack them row-wise.

    Parameters
    ----------
    delta_phi_df : pd.DataFrame
        Columns ``time`` (UTC-aware) and ``delta_phi`` (float).
    flare_df : pd.DataFrame
        Must contain ``onset_time`` column (UTC-aware).
    pre_hours, post_hours : float
        Hours before / after onset to include in each window.

    Returns
    -------
    rel_hours : np.ndarray
        Relative-time axis (hours); shape ``(n_times,)``.
    matrix : np.ndarray
        Stacked windows; shape ``(n_flares_kept, n_times)``.
        Values that fall outside the data range are NaN.
    n_flares_kept : int
        Number of flare events with at least one valid sample.
    """
    sig = delta_phi_df[["time", "delta_phi"]].dropna().sort_values("time").reset_index(drop=True)
    sig["time"] = pd.to_datetime(sig["time"], utc=True)
    sig_times = sig["time"].to_numpy()
    sig_vals = np.abs(sig["delta_phi"].to_numpy(dtype=float))

    # Infer cadence
    dt_seconds = float(
        np.median(np.diff(sig_times).astype("timedelta64[s]").astype(float))
    )
    dt_minutes = dt_seconds / 60.0
    if not np.isfinite(dt_minutes) or dt_minutes <= 0:
        raise RuntimeError("Could not infer cadence from time column.")

    n_times = int(round((pre_hours + post_hours) * 60 / dt_minutes)) + 1
    rel_minutes = np.linspace(-pre_hours * 60, post_hours * 60, n_times)
    rel_hours = rel_minutes / 60.0

    flare_df = flare_df.copy()
    flare_df["onset_time"] = pd.to_datetime(flare_df["onset_time"], utc=True)

    windows: list[np.ndarray] = []
    for onset in flare_df["onset_time"]:
        target_times = onset + pd.to_timedelta(rel_minutes, unit="m")
        target_np = target_times.to_numpy()

        idx = np.searchsorted(sig_times, target_np, side="left")
        idx = np.clip(idx, 0, len(sig_times) - 1)
        idx2 = np.clip(idx - 1, 0, len(sig_times) - 1)

        t1 = sig_times[idx]
        t0 = sig_times[idx2]
        choose_idx2 = (
            np.abs((target_np - t0).astype("timedelta64[s]").astype(float))
            < np.abs((t1 - target_np).astype("timedelta64[s]").astype(float))
        )
        final_idx = np.where(choose_idx2, idx2, idx)
        window = sig_vals[final_idx].astype(float)

        # Mark samples too far from the nearest data point as NaN
        nearest_times = sig_times[final_idx]
        lag_s = np.abs(
            (nearest_times - target_np).astype("timedelta64[s]").astype(float)
        )
        window[lag_s > 1.5 * dt_seconds] = np.nan

        if np.isfinite(window).sum() > 0:
            windows.append(window)

    matrix = np.vstack(windows) if windows else np.empty((0, n_times))
    return rel_hours, matrix, len(windows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def make_figure(
    months: int = 1,
    pre_hours: float = 24.0,
    post_hours: float = 6.0,
    output_dir: Path = _OUTPUT_DIR,
) -> Path:
    """Generate and save the superposed-epoch figure.

    Returns the path of the saved PNG.
    """
    start_dt = _T0
    end_dt = _T0 + timedelta(days=30 * months)

    print(f"[superposed_epoch] Loading XRS data ({start_dt.date()} – {end_dt.date()}) …")
    xrs_df = _load_xrs_slice(_DEFAULT_ZIP, start_dt, end_dt)
    print(f"[superposed_epoch] {len(xrs_df):,} XRS rows loaded")

    print("[superposed_epoch] Computing ΔΦ(t) …")
    delta_phi_df = _compute_delta_phi_from_xrs(xrs_df)

    print("[superposed_epoch] Detecting flares from XRS peaks …")
    flare_df = _detect_flares_from_xrs(xrs_df)
    print(f"[superposed_epoch] {len(flare_df)} flare-like events detected")

    print("[superposed_epoch] Building superposed-epoch matrix …")
    rel_hours, matrix, n_kept = build_superposed_epoch_matrix(
        delta_phi_df, flare_df, pre_hours=pre_hours, post_hours=post_hours,
    )
    print(f"[superposed_epoch] Matrix shape: {matrix.shape} ({n_kept} flares kept)")

    # Ensemble statistics
    mean = np.nanmean(matrix, axis=0)
    n_eff = np.sum(np.isfinite(matrix), axis=0).astype(float)
    std = np.nanstd(matrix, axis=0, ddof=1)
    sem = std / np.sqrt(np.maximum(n_eff, 1.0))
    ci = 1.96 * sem

    # Plot
    fig, ax = plot_superposed_epoch(
        rel_hours,
        mean,
        ci,
        n_flares=n_kept,
        title=(
            f"Superposed-epoch mean of |ΔΦ(t)| around flare onset "
            f"({start_dt.strftime('%b %Y')})"
            if months == 1
            else (
                f"Superposed-epoch mean of |ΔΦ(t)| around flare onset "
                f"({start_dt.strftime('%b %Y')} – {end_dt.strftime('%b %Y')})"
            )
        ),
    )
    fig.tight_layout()

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "fig9_superposed_epoch.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[superposed_epoch] Saved → {out_path}")
    return out_path


def main(argv: "list[str] | None" = None) -> None:
    parser = argparse.ArgumentParser(
        description="Generate the superposed-epoch mean |ΔΦ(t)| figure.",
    )
    parser.add_argument(
        "--months", type=int, default=1, metavar="N",
        help="Number of months of GOES-18 data to analyse (default: 1).",
    )
    parser.add_argument(
        "--pre-hours", type=float, default=24.0, metavar="H",
        help="Hours before flare onset to include (default: 24).",
    )
    parser.add_argument(
        "--post-hours", type=float, default=6.0, metavar="H",
        help="Hours after flare onset to include (default: 6).",
    )
    args = parser.parse_args(argv)

    make_figure(months=args.months, pre_hours=args.pre_hours, post_hours=args.post_hours)


if __name__ == "__main__":
    main()
