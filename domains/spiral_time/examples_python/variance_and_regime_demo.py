"""
variance_and_regime_demo.py
===========================
Demonstrates the triadic instability operator ΔΦ(t) and regime classification
using real GOES multi-channel data.

Physical background
-------------------
Rolling variance Var_L[X](t) — PAPER.md Eq. (3):

    Var_L[X](t) = (1/L) Σ_{i=0}^{L-1} (X(t-i) - X̄_L(t))²

Triadic instability operator — PAPER.md Eq. (6):

    ΔΦ(t) = α|ΔS(t)| + β|ΔI(t)| + γ|ΔC(t)|

where:
    S(t) = Var_L[B](t)   — structural variability (magnetometer rolling variance)
    I(t) = Var_L[X](t)   — informational complexity (X-ray rolling variance)
    C(t) = rolling Pearson correlation between X(t) and EUV(t) — cross-channel coherence
    ΔS, ΔI, ΔC = first differences of S, I, C

Regime classification thresholds — PAPER.md §6.4 (applied after normalization to [0,1]):
    Isostasis      ΔΦ < 0.15
    Allostasis     0.15 ≤ ΔΦ < 0.35
    High-Allostasis 0.35 ≤ ΔΦ < 0.40
    Collapse       ΔΦ ≥ 0.40

Note: α = β = γ = 1/3 (equal weighting) is used as a placeholder.
      PAPER.md states these are calibrated from historical flare catalogues.

Output: domains/spiral_time/examples_python/output/variance_and_regime_demo.png

Usage
-----
    python domains/spiral_time/examples_python/variance_and_regime_demo.py
"""

import os
import sys
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# Allow running from any working directory
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, _REPO_ROOT)

from shared.data_loader import load_xray_flux, load_magnetometer, load_euvs
from shared.math_utils import (
    rolling_variance,
    rolling_correlation,
    normalize_01,
    classify_regime,
    REGIME_BOUNDS,
    REGIME_COLORS,
    REGIME_LABELS,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
WINDOW_L = 30          # rolling-variance window length (data points)
ALPHA = BETA = GAMMA = 1 / 3   # equal weighting — placeholder (see PAPER.md §6.4)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "variance_and_regime_demo.png")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Loading data …")
    df_x = load_xray_flux()
    df_b = load_magnetometer()
    df_e = load_euvs()

    # Align on common timestamps via merge (inner join keeps only shared times)
    df = df_x.rename(columns={"flux": "X"}).merge(
        df_b.rename(columns={"He": "B"}), on="time", how="inner"
    )

    # Pick first numeric EUV channel
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

    print(f"  {len(df)} aligned data points across all channels.")

    # --- Compute S(t), I(t), C(t) ---
    S = rolling_variance(B, WINDOW_L)     # structural variability
    I = rolling_variance(X, WINDOW_L)     # informational complexity
    C = rolling_correlation(X, EUV, WINDOW_L)  # cross-channel coherence

    # --- First differences ---
    dS = np.abs(np.diff(S, prepend=np.nan))
    dI = np.abs(np.diff(I, prepend=np.nan))
    dC = np.abs(np.diff(C, prepend=np.nan))

    # --- ΔΦ(t) — PAPER.md Eq. (6) ---
    delta_phi = ALPHA * dS + BETA * dI + GAMMA * dC

    # --- Normalize to [0, 1] before applying thresholds ---
    delta_phi_norm = normalize_01(delta_phi)

    # --- Regime classification ---
    regimes = np.array([classify_regime(v) for v in delta_phi_norm])

    # ---------------------------------------------------------------------------
    # Plot
    # ---------------------------------------------------------------------------
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    fig.suptitle("Triadic Instability Operator ΔΦ(t) — PAPER.md Eqs. (3), (6), §6.4",
                 fontsize=13)

    # Panel 1: X-ray flux
    ax1.semilogy(times, X, color="#2980b9", linewidth=0.8, label="X-ray flux X(t)")
    ax1.set_ylabel("Flux (W m⁻²)")
    ax1.set_title("GOES X-ray Flux (0.1–0.8 nm)")
    ax1.legend(loc="upper right", fontsize=9)
    ax1.grid(True, alpha=0.3)

    # Panel 2: ΔΦ(t) with regime bands
    band_limits = [0.0] + REGIME_BOUNDS + [1.0]
    for i, (lo, hi) in enumerate(zip(band_limits[:-1], band_limits[1:])):
        ax2.axhspan(lo, hi, color=REGIME_COLORS[i], alpha=0.15)
    for thresh, label in zip(REGIME_BOUNDS, REGIME_LABELS[1:]):
        ax2.axhline(thresh, color="gray", linewidth=0.8, linestyle="--")

    ax2.plot(times, delta_phi_norm, color="#8e44ad", linewidth=0.8,
             label="ΔΦ(t) normalized")
    ax2.set_ylim(0, 1)
    ax2.set_ylabel("ΔΦ(t) [normalized]")
    ax2.set_xlabel("Time")
    ax2.set_title("Instability Operator ΔΦ(t) with Regime Classification")

    # Legend patches for regimes
    patches = [mpatches.Patch(color=c, alpha=0.4, label=l)
               for c, l in zip(REGIME_COLORS, REGIME_LABELS)]
    ax2.legend(handles=patches + [plt.Line2D([0], [0], color="#8e44ad", label="ΔΦ(t)")],
               loc="upper right", fontsize=9)
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(OUTPUT_FILE, dpi=150, bbox_inches="tight")
    print(f"Figure saved → {OUTPUT_FILE}")
    plt.close()


if __name__ == "__main__":
    main()
