"""
make_goes_figures.py — Publication-ready GOES X-ray figures for PAPER.md.

Loads real GOES 7-day observational data and produces three figures suitable
for inclusion in a scientific paper.

Figures produced
----------------
Figure 6  fig6_goes_xray_flux.png        — GOES 0.1–0.8 nm semilog time series
Figure 7  fig7_windowed_variance.png     — Rolling/windowed variance (L=200)
Figure 8  fig8_flare_event_overlay.png   — Flux time series with flare markers

Output directory
----------------
output/paper_figures/   (created automatically if absent)

Usage
-----
    python domains/spiral_time/examples_python/make_goes_figures.py

Dependencies: numpy, matplotlib, pandas (see requirements.txt)
"""

import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# Ensure repo root is on the path regardless of working directory.
_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from shared.data_loader import load_xray_flux, load_xray_flares
from shared.math_utils import rolling_variance

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

WINDOW_L = 200
_OUTPUT_DIR = os.path.join(_REPO_ROOT, "output", "paper_figures")
_TIME_FMT = "%m-%d\n%H:%M"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_flux():
    """Load GOES 0.1–0.8 nm X-ray flux and return (times, flux) arrays.

    Returns
    -------
    times : list[datetime]
        UTC timestamps.
    flux : np.ndarray
        X-ray flux values in W m⁻².
    """
    df = load_xray_flux()
    times = df["time"].tolist()
    flux = df["flux"].to_numpy(dtype=float)
    return times, flux


def _load_flare_times():
    """Load NOAA flare catalogue and return list of UTC onset datetimes.

    Uses ``begin_time`` as the flare onset when available; falls back to
    ``time_max`` for records where ``begin_time`` is None.

    Returns
    -------
    list[datetime]
        UTC timestamps of flare onsets (None values excluded).
    """
    df = load_xray_flares()
    onset_times = []
    for _, row in df.iterrows():
        onset_time = row["time_begin"] if row["time_begin"] is not None else row["time_max"]
        if onset_time is not None:
            onset_times.append(onset_time)
    return onset_times


# ---------------------------------------------------------------------------
# Figure helpers
# ---------------------------------------------------------------------------

def _apply_utc_xaxis(ax):
    """Format x-axis as UTC dates with the required tick label format."""
    ax.xaxis.set_major_formatter(mdates.DateFormatter(_TIME_FMT))
    ax.figure.autofmt_xdate(rotation=0, ha="center")


# ---------------------------------------------------------------------------
# Figure 6 — GOES X-ray flux time series
# ---------------------------------------------------------------------------

def make_fig6(times, flux):
    """Figure 6: semilog GOES 0.1–0.8 nm X-ray flux time series.

    Parameters
    ----------
    times : list[datetime]
        UTC timestamps.
    flux : np.ndarray
        X-ray flux values in W m⁻².

    Returns
    -------
    fig : matplotlib.figure.Figure
    path : str
        Absolute path of the saved PNG.
    """
    fig, ax = plt.subplots(facecolor="white")
    ax.set_facecolor("white")

    ax.semilogy(times, flux, color="#2271b3", linewidth=0.8,
                label="GOES 0.1–0.8 nm X-ray flux")

    ax.set_ylabel("X-ray flux (W m⁻²)")
    ax.set_xlabel("UTC")
    ax.set_title("GOES 0.1–0.8 nm X-ray flux")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(True, which="both", alpha=0.25)

    _apply_utc_xaxis(ax)
    fig.tight_layout()

    path = os.path.join(_OUTPUT_DIR, "fig6_goes_xray_flux.png")
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# Figure 7 — Rolling/windowed variance
# ---------------------------------------------------------------------------

def make_fig7(times, flux):
    """Figure 7: rolling variance of X-ray flux with window length L=200.

    Parameters
    ----------
    times : list[datetime]
        UTC timestamps.
    flux : np.ndarray
        X-ray flux values in W m⁻².

    Returns
    -------
    path : str
        Absolute path of the saved PNG.
    """
    var = rolling_variance(flux, WINDOW_L)

    fig, ax = plt.subplots(facecolor="white")
    ax.set_facecolor("white")

    ax.plot(times, var, color="#d62728", linewidth=0.8,
            label=f"Rolling variance (L={WINDOW_L})")

    ax.set_ylabel("Variance (W² m⁻⁴)")
    ax.set_xlabel("UTC")
    ax.set_title(f"Rolling variance of GOES X-ray flux (L={WINDOW_L})")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(True, alpha=0.25)

    _apply_utc_xaxis(ax)
    fig.tight_layout()

    path = os.path.join(_OUTPUT_DIR, "fig7_windowed_variance.png")
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# Figure 8 — Flare-event overlay
# ---------------------------------------------------------------------------

def make_fig8(times, flux, flare_times):
    """Figure 8: semilog X-ray flux with vertical lines at flare onsets.

    Parameters
    ----------
    times : list[datetime]
        UTC timestamps.
    flux : np.ndarray
        X-ray flux values in W m⁻².
    flare_times : list[datetime]
        UTC onset times of flare events.

    Returns
    -------
    path : str
        Absolute path of the saved PNG.
    """
    fig, ax = plt.subplots(facecolor="white")
    ax.set_facecolor("white")

    ax.semilogy(times, flux, color="#2271b3", linewidth=0.8,
                label="GOES 0.1–0.8 nm X-ray flux")

    for i, ft in enumerate(flare_times):
        label = "Flare onset" if i == 0 else None
        ax.axvline(ft, color="#e74c3c", linewidth=0.8, alpha=0.7,
                   linestyle="--", label=label)

    ax.set_ylabel("X-ray flux (W m⁻²)")
    ax.set_xlabel("UTC")
    ax.set_title("GOES X-ray flux with flare-event overlay")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(True, which="both", alpha=0.25)

    _apply_utc_xaxis(ax)
    fig.tight_layout()

    path = os.path.join(_OUTPUT_DIR, "fig8_flare_event_overlay.png")
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    os.makedirs(_OUTPUT_DIR, exist_ok=True)

    print("Loading GOES X-ray flux …")
    times, flux = _load_flux()
    print(f"  {len(times)} data points loaded.")

    print("Loading NOAA flare catalogue …")
    flare_times = _load_flare_times()
    print(f"  {len(flare_times)} flare event(s) found.")

    print("Generating figures …")
    p6 = make_fig6(times, flux)
    p7 = make_fig7(times, flux)
    p8 = make_fig8(times, flux, flare_times)

    print("\nSaved figures:")
    for path in (p6, p7, p8):
        print(os.path.abspath(path))
