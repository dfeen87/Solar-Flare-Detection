"""
composite_indicator_demo.py
===========================
Demonstrates the composite instability indicator I(t) from PAPER.md Eq. (5),
combining rolling variance of X-ray flux and magnetometer data with the EUV
time-derivative.

Physical background
-------------------
Rolling variance — PAPER.md Eq. (3):

    Var_L[X](t) = (1/L) Σ_{i=0}^{L-1} (X(t-i) - X̄_L(t))²

Composite indicator — PAPER.md Eq. (5):

    I(t) = w₁ Var_L[X](t) + w₂ Var_L[B](t) + w₃ |d/dt EUV(t)|

where weights w₁ = w₂ = w₃ = 1/3 are used as equal-weight placeholders.
PAPER.md states these weights are calibrated from historical flare catalogues.

Each component is normalized to [0, 1] before combining so that equal weights
are physically meaningful.

Output: domains/energy_transfer/examples_python/output/composite_indicator_demo.png

Usage
-----
    python domains/energy_transfer/examples_python/composite_indicator_demo.py
"""

import os
import sys
import numpy as np
import matplotlib.pyplot as plt

# Allow running from any working directory
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, _REPO_ROOT)

from shared.data_loader import load_xray_flux, load_magnetometer, load_euvs
from shared.math_utils import rolling_variance, euv_derivative, normalize_01, compute_composite_indicator

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
WINDOW_L = 30          # rolling-variance window length (data points)
W1 = W2 = W3 = 1 / 3  # equal weighting — placeholder (see PAPER.md Eq. (5))

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "composite_indicator_demo.png")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Loading data …")
    df_x = load_xray_flux()
    df_b = load_magnetometer()
    df_e = load_euvs()

    # Align on common timestamps
    df = df_x.rename(columns={"flux": "X"}).merge(
        df_b.rename(columns={"He": "B"}), on="time", how="inner"
    )
    euv_cols = [c for c in df_e.columns if c != "time"]
    if not euv_cols:
        raise RuntimeError("No EUV channels found in euvs data.")
    df = df.merge(df_e[["time", euv_cols[0]]].rename(columns={euv_cols[0]: "EUV"}),
                  on="time", how="inner")

    df.sort_values("time", inplace=True)
    df.reset_index(drop=True, inplace=True)

    X = df["X"].to_numpy(dtype=float)
    B = df["B"].to_numpy(dtype=float)
    EUV = df["EUV"].to_numpy(dtype=float)
    times = df["time"].to_numpy()

    print(f"  {len(df)} aligned data points.")

    # --- Individual components ---
    var_x = rolling_variance(X, WINDOW_L)   # Var_L[X](t)
    var_b = rolling_variance(B, WINDOW_L)   # Var_L[B](t)
    d_euv = euv_derivative(EUV)             # |d/dt EUV(t)|

    # --- Normalize each component to [0, 1] ---
    var_x_n = normalize_01(var_x)
    var_b_n = normalize_01(var_b)
    d_euv_n = normalize_01(d_euv)

    # --- Composite indicator I(t) — PAPER.md Eq. (5) ---
    indicator = compute_composite_indicator(var_x_n, var_b_n, d_euv_n, W1, W2, W3)

    # ---------------------------------------------------------------------------
    # Plot
    # ---------------------------------------------------------------------------
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    fig.suptitle("Composite Indicator I(t) — PAPER.md Eqs. (3), (5)", fontsize=13)

    # Panel 1: Individual normalized components
    ax1.plot(times, var_x_n, color="#2980b9", linewidth=0.8,
             label="Var_L[X] (normalized)")
    ax1.plot(times, var_b_n, color="#27ae60", linewidth=0.8,
             label="Var_L[B] (normalized)")
    ax1.plot(times, d_euv_n, color="#e67e22", linewidth=0.8,
             label="|d/dt EUV| (normalized)")
    ax1.set_ylabel("Component value [0–1]")
    ax1.set_title("Normalized Components of I(t)")
    ax1.legend(loc="upper right", fontsize=9)
    ax1.grid(True, alpha=0.3)
    ax1.set_ylim(-0.05, 1.05)

    # Panel 2: Composite indicator
    ax2.plot(times, indicator, color="#8e44ad", linewidth=1.0, label="I(t) composite")
    ax2.set_ylabel("I(t)")
    ax2.set_xlabel("Time")
    ax2.set_title("Composite Instability Indicator I(t) [w₁=w₂=w₃=1/3]")
    ax2.legend(loc="upper right", fontsize=9)
    ax2.grid(True, alpha=0.3)
    ax2.set_ylim(-0.05, 1.05)

    plt.tight_layout()
    plt.savefig(OUTPUT_FILE, dpi=150, bbox_inches="tight")
    print(f"Figure saved → {OUTPUT_FILE}")
    plt.close()


if __name__ == "__main__":
    main()
