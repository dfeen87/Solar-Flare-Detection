"""
make_fig6_goes_flux.py — Standalone Figure 6: GOES 0.1–0.8 nm X-ray flux.

Loads real GOES 7-day X-ray flux via the shared loader layer and produces a
single publication-ready semilog time-series plot.

Figure produced
---------------
Figure 6  fig6_goes_xray_flux.png  — GOES 0.1–0.8 nm semilog time series

Output directory
----------------
output/paper_figures/   (created automatically if absent)

Usage
-----
    python domains/spiral_time/examples_python/make_fig6_goes_flux.py
"""

import os
import sys

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

from shared.data_loader import load_xray_flux

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_OUTPUT_DIR = os.path.join(_REPO_ROOT, "output", "paper_figures")
_TIME_FMT = "%m-%d\n%H:%M"


# ---------------------------------------------------------------------------
# Figure 6 — GOES X-ray flux time series
# ---------------------------------------------------------------------------

def make_fig6(times, flux):
    """Figure 6: semilog GOES 0.1–0.8 nm X-ray flux time series.

    Parameters
    ----------
    times : list[datetime]
        UTC timestamps.
    flux : numpy.ndarray
        X-ray flux values in W m⁻².

    Returns
    -------
    path : str
        Absolute path of the saved PNG.
    """
    fig, ax = plt.subplots(facecolor="white")
    ax.set_facecolor("white")

    ax.semilogy(times, flux, color="#2271b3", linewidth=0.8)

    ax.set_title("GOES 0.1–0.8 nm X-ray flux")
    ax.set_ylabel("X-ray flux (W/m²)")
    ax.set_xlabel("UTC time")
    ax.grid(True, which="both", alpha=0.25)

    ax.xaxis.set_major_formatter(mdates.DateFormatter(_TIME_FMT))
    fig.autofmt_xdate(rotation=0, ha="center")
    fig.tight_layout()

    path = os.path.join(_OUTPUT_DIR, "fig6_goes_xray_flux.png")
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return os.path.abspath(path)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    os.makedirs(_OUTPUT_DIR, exist_ok=True)

    df = load_xray_flux()
    times = df["time"].tolist()
    flux = df["flux"].to_numpy(dtype=float)

    path = make_fig6(times, flux)
    print(path)
