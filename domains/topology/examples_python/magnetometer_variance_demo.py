"""
magnetometer_variance_demo.py
=============================
Demonstrates rolling variance of the magnetometer B(t) signal and the memory
variable χ(t) from PAPER.md §6.3.

Physical background
-------------------
Rolling variance — PAPER.md Eq. (3) applied to B(t):

    Var_L[B](t) = (1/L) Σ_{i=0}^{L-1} (B(t-i) - B̄_L(t))²

Memory variable χ(t) — PAPER.md §6.3:

    χ(t) approximated as the cumulative (trapezoidal) integral of Var_L[B](t):

    χ(t) ≈ ∫₀ᵗ Var_L[B](τ) dτ

    PAPER.md §6.3: "χ(t) may be approximated by time-integrated magnetic
    variability measures."

Output: domains/topology/examples_python/output/magnetometer_variance_demo.png

Usage
-----
    python domains/topology/examples_python/magnetometer_variance_demo.py
"""

import os
import sys
import numpy as np
import matplotlib.pyplot as plt

# Allow running from any working directory
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, _REPO_ROOT)

from shared.data_loader import load_magnetometer
from shared.math_utils import rolling_variance, compute_chi

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
WINDOW_L = 30   # rolling-variance window length (data points)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "magnetometer_variance_demo.png")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Loading magnetometer data …")
    df_b = load_magnetometer()
    df_b.sort_values("time", inplace=True)
    df_b.reset_index(drop=True, inplace=True)

    B = df_b["He"].to_numpy(dtype=float)
    times = df_b["time"].to_numpy()

    print(f"  {len(df_b)} magnetometer data points.")

    # --- Rolling variance Var_L[B](t) ---
    var_b = rolling_variance(B, WINDOW_L)

    # --- Memory variable χ(t) ---
    chi = compute_chi(var_b, WINDOW_L)

    # ---------------------------------------------------------------------------
    # Plot
    # ---------------------------------------------------------------------------
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
    fig.suptitle("Magnetometer Variance and Memory Variable χ(t) — PAPER.md Eq. (3), §6.3",
                 fontsize=13)

    # Panel 1: Raw B(t)
    ax1.plot(times, B, color="#27ae60", linewidth=0.8, label="B(t) — He component")
    ax1.set_ylabel("B(t) [nT]")
    ax1.set_title("Raw Magnetometer Signal B(t)")
    ax1.legend(loc="upper right", fontsize=9)
    ax1.grid(True, alpha=0.3)

    # Panel 2: Rolling variance
    ax2.plot(times, var_b, color="#e67e22", linewidth=0.8,
             label=f"Var_L[B](t)  L={WINDOW_L}")
    ax2.set_ylabel("Variance")
    ax2.set_title(f"Rolling Variance Var_L[B](t)  (L = {WINDOW_L})")
    ax2.legend(loc="upper right", fontsize=9)
    ax2.grid(True, alpha=0.3)

    # Panel 3: Memory variable χ(t)
    ax3.plot(times, chi, color="#8e44ad", linewidth=0.8, label="χ(t) — cumulative integral")
    ax3.set_ylabel("χ(t) [cumulative]")
    ax3.set_xlabel("Time")
    ax3.set_title("Memory Variable χ(t) = ∫ Var_L[B] dt  (PAPER.md §6.3)")
    ax3.legend(loc="upper right", fontsize=9)
    ax3.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(OUTPUT_FILE, dpi=150, bbox_inches="tight")
    print(f"Figure saved → {OUTPUT_FILE}")
    plt.close()


if __name__ == "__main__":
    main()
