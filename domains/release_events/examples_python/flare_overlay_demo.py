"""
flare_overlay_demo.py
=====================
Overlays GOES flare event catalogue timestamps onto X-ray flux and rolling
variance plots — implementing the event overlay analysis from PAPER.md §9.3,
Figures 6–8.

Physical background
-------------------
Rolling variance — PAPER.md Eq. (3):

    Var_L[X](t) = (1/L) Σ_{i=0}^{L-1} (X(t-i) - X̄_L(t))²

Flare events {tₖ} are catalogued by GOES class (A, B, C, M, X).
Vertical lines at each {tₖ} allow visual assessment of how well
Var_L[X](t) precedes flare onset — the lead-time analysis of PAPER.md §9.3.

Output: domains/release_events/examples_python/output/flare_overlay_demo.png

References: PAPER.md §9.3, Figures 6–8.

Usage
-----
    python domains/release_events/examples_python/flare_overlay_demo.py
"""

import os
import sys
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.lines as mlines

# Allow running from any working directory
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, _REPO_ROOT)

from shared.data_loader import load_xray_flux, load_xray_flares
from shared.math_utils import rolling_variance

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
WINDOW_L = 30   # rolling-variance window length

# Flare class colours (PAPER.md §9.3 convention)
CLASS_COLORS = {
    "X": "#e74c3c",   # red
    "M": "#e67e22",   # orange
    "C": "#f1c40f",   # yellow
    "B": "#95a5a6",   # gray
    "A": "#bdc3c7",   # light gray
}

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "flare_overlay_demo.png")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Loading X-ray flux and flare catalogue …")
    df_x = load_xray_flux()
    df_f = load_xray_flares()

    df_x.sort_values("time", inplace=True)
    df_x.reset_index(drop=True, inplace=True)

    X = df_x["flux"].to_numpy(dtype=float)
    times = df_x["time"].to_numpy()

    print(f"  {len(df_x)} X-ray data points.")
    print(f"  {len(df_f)} flare events in catalogue.")

    # --- Rolling variance ---
    var_x = rolling_variance(X, WINDOW_L)

    # Determine flux time range for filtering flare events
    t_min = df_x["time"].min()
    t_max = df_x["time"].max()
    mask = (df_f["time_begin"] >= t_min) & (df_f["time_begin"] <= t_max)
    df_f_window = df_f[mask].copy()
    print(f"  {len(df_f_window)} flare events within flux time window.")

    # ---------------------------------------------------------------------------
    # Plot
    # ---------------------------------------------------------------------------
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 9), sharex=True)
    fig.suptitle(
        "Flare Event Overlay — PAPER.md §9.3, Figures 6–8", fontsize=13
    )

    def _draw_flare_lines(ax):
        """Draw vertical lines for each flare event, colour-coded by class."""
        for _, row in df_f_window.iterrows():
            cls = str(row["class_type"]).upper()
            color = CLASS_COLORS.get(cls, "#7f8c8d")
            ax.axvline(row["time_begin"], color=color, linewidth=0.8, alpha=0.7)

    # Panel 1: X-ray flux
    ax1.semilogy(times, X, color="#2980b9", linewidth=0.7, label="X-ray flux X(t)")
    _draw_flare_lines(ax1)
    ax1.set_ylabel("Flux (W m⁻²)")
    ax1.set_title("GOES X-ray Flux with Flare Event Timestamps")
    ax1.grid(True, alpha=0.3)

    # Panel 2: Rolling variance
    ax2.plot(times, var_x, color="#e67e22", linewidth=0.7,
             label=f"Var_L[X](t)  L={WINDOW_L}")
    _draw_flare_lines(ax2)
    ax2.set_ylabel("Var_L[X](t)")
    ax2.set_xlabel("Time")
    ax2.set_title(f"Rolling Variance Var_L[X](t)  (L = {WINDOW_L})")
    ax2.grid(True, alpha=0.3)

    # Shared legend for flare classes
    legend_handles = [
        mlines.Line2D([], [], color=col, linewidth=1.5, label=f"Class {cls}")
        for cls, col in CLASS_COLORS.items()
    ]
    fig.legend(handles=legend_handles, loc="lower center", ncol=5,
               fontsize=9, title="Flare Class", bbox_to_anchor=(0.5, 0.0))

    plt.tight_layout(rect=(0, 0.05, 1, 1))
    plt.savefig(OUTPUT_FILE, dpi=150, bbox_inches="tight")
    print(f"Figure saved → {OUTPUT_FILE}")
    plt.close()


if __name__ == "__main__":
    main()
