"""
full_pipeline_demo.py — Unified cross-domain PAPER.md pipeline demonstration.

Loads all five GOES data products, computes every metric defined in PAPER.md,
classifies the current solar activity regime, and produces a four-panel summary
figure.

Scientific pipeline
-------------------
All equations refer to Krüger & Feeney (2026), PAPER.md.

1.  Load data (§4.1, Table 1)
    - X-ray flux X(t)          → shared.data_loader.load_xray_flux()
    - Flare catalogue          → shared.data_loader.load_xray_flares()
    - Magnetometer B(t)        → shared.data_loader.load_magnetometer()
    - EUV irradiance EUV(t)    → shared.data_loader.load_euvs()
    - X-ray background         → shared.data_loader.load_xray_background()

2.  Compute variance components (Eq. 3)
    - Var_L[X](t) = rolling_variance(X, L)
    - Var_L[B](t) = rolling_variance(B, L)

3.  Compute EUV derivative (Eq. 5 — third term)
    - |d/dt EUV(t)| = euv_derivative(EUV)

4.  Normalize all components (§5)
    - Each component → normalize_01()

5.  Composite instability indicator I(t) (Eq. 5)
    - I(t) = w₁ Var_L[X] + w₂ Var_L[B] + w₃ |d/dt EUV|

6.  Cross-channel coherence C(t) (§6.2)
    - C(t) = rolling_correlation(X, EUV, L)

7.  Triadic instability operator ΔΦ(t) (Eq. 6)
    - ΔΦ(t) = α|ΔS(t)| + β|ΔI(t)| + γ|ΔC(t)|

8.  Regime classification (§6.4)
    - classify_regime(ΔΦ_norm[-1])

9.  Memory variable χ(t) (§6.3)
    - χ(t) ≈ ∫₀ᵗ Var_L[B](τ) dτ

10. Phase–memory embedding ψ(t) (Eq. 7)
    - φ(t) proxy = normalize_01(C(t))
    - χ(t) from step 9

Output
------
- Saves a four-panel figure to:
    domains/spiral_time/examples_python/output/full_pipeline_demo.png
- Prints regime classification and summary statistics to stdout.

Usage
-----
    python domains/spiral_time/examples_python/full_pipeline_demo.py

Dependencies: numpy, matplotlib, pandas (see requirements.txt)
"""

import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Ensure repo root is on the path regardless of working directory.
_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from shared.data_loader import (
    load_xray_flux,
    load_xray_flares,
    load_magnetometer,
    load_euvs,
    load_xray_background,
)
from shared.math_utils import (
    rolling_variance,
    normalize_01,
    euv_derivative,
    rolling_correlation,
    compute_composite_indicator,
    compute_delta_phi,
    classify_regime,
    compute_chi,
)
from shared.plot_utils import (
    plot_flare_overlay,
    plot_rolling_variance,
    plot_delta_phi,
    plot_psi_trajectory,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

#: Rolling-window length L (data points).  One data point ≈ 1 minute for
#: GOES 1-minute data, so L=30 corresponds to a 30-minute rolling window.
WINDOW_L: int = 30

#: Equal weighting coefficients for ΔΦ and I(t).
ALPHA = BETA = GAMMA = 1 / 3
W1 = W2 = W3 = 1 / 3

#: Output path for the figure.
_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
_OUTPUT_FILE = os.path.join(_OUTPUT_DIR, "full_pipeline_demo.png")


# ---------------------------------------------------------------------------
# Helper: align multiple DataFrames on their common timestamps
# ---------------------------------------------------------------------------

def _align(*dataframes):
    """Inner-join all DataFrames on their 'time' column and return arrays.

    Returns (times, *value_arrays) where *times* is a numpy array of the
    common timestamps and each *value_array* corresponds to the non-time
    column of the respective DataFrame.
    """
    import pandas as pd

    merged = dataframes[0].copy()
    for df in dataframes[1:]:
        merged = merged.merge(df, on="time", how="inner")
    merged = merged.sort_values("time").reset_index(drop=True)
    times = merged["time"].to_numpy()
    cols = [c for c in merged.columns if c != "time"]
    return (times,) + tuple(merged[c].to_numpy(dtype=float) for c in cols)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_pipeline():
    """Execute the full PAPER.md pipeline and return all outputs."""
    print("=" * 60)
    print("Solar Flare Detection — Full Pipeline Demo")
    print("PAPER.md: Krüger & Feeney (2026)")
    print("=" * 60)

    # ------------------------------------------------------------------
    # Step 1 — Load data
    # ------------------------------------------------------------------
    print("\n[1/10] Loading GOES data products …")
    df_x = load_xray_flux()                      # columns: time, flux
    df_f = load_xray_flares()                    # columns: time_begin, …, class_type
    df_b = load_magnetometer()                   # columns: time, He
    df_e = load_euvs()                           # columns: time, <channels>
    load_xray_background()                       # loaded for completeness; not used below

    # Pick the first EUV channel that is not 'time'.
    euv_col = [c for c in df_e.columns if c != "time"][0]

    # Rename columns to canonical names before merging.
    df_x = df_x.rename(columns={"flux": "X"})
    df_b = df_b.rename(columns={"He": "B"})
    df_e = df_e[["time", euv_col]].rename(columns={euv_col: "EUV"})

    print(f"   X-ray records  : {len(df_x)}")
    print(f"   Magnetometer   : {len(df_b)}")
    print(f"   EUV records    : {len(df_e)}")
    print(f"   Flare events   : {len(df_f)}")

    # ------------------------------------------------------------------
    # Step 2 — Align on common timestamps
    # ------------------------------------------------------------------
    print("\n[2/10] Aligning time axes …")
    times, X, B, EUV = _align(df_x, df_b, df_e)
    print(f"   Common time steps: {len(times)}")

    # ------------------------------------------------------------------
    # Steps 2–4 — Variance, derivative, normalization
    # ------------------------------------------------------------------
    print(f"\n[3/10] Computing rolling variance (L={WINDOW_L}) …")
    var_x = rolling_variance(X, WINDOW_L)
    var_b = rolling_variance(B, WINDOW_L)

    print("[4/10] Computing EUV derivative …")
    d_euv = euv_derivative(EUV)

    print("[5/10] Normalizing components to [0, 1] …")
    var_x_norm = normalize_01(var_x)
    var_b_norm = normalize_01(var_b)
    d_euv_norm = normalize_01(d_euv)

    # ------------------------------------------------------------------
    # Steps 5–7 — I(t), C(t), ΔΦ(t)
    # ------------------------------------------------------------------
    print("[6/10] Computing composite indicator I(t) — Eq. (5) …")
    indicator = compute_composite_indicator(
        var_x_norm, var_b_norm, d_euv_norm, w1=W1, w2=W2, w3=W3
    )

    print("[7/10] Computing rolling correlation C(t) …")
    corr = rolling_correlation(X, EUV, WINDOW_L)

    print("[8/10] Computing triadic instability operator ΔΦ(t) — Eq. (6) …")
    delta_phi = compute_delta_phi(var_b, var_x, corr, ALPHA, BETA, GAMMA)
    delta_phi_norm = normalize_01(delta_phi)

    # ------------------------------------------------------------------
    # Step 8 — Regime classification
    # ------------------------------------------------------------------
    print("[9/10] Classifying solar activity regime (§6.4) …")
    valid_vals = delta_phi_norm[~np.isnan(delta_phi_norm)]
    if len(valid_vals) == 0:
        regime = "Isostasis"
    else:
        regime = classify_regime(float(valid_vals[-1]))

    # ------------------------------------------------------------------
    # Steps 9–10 — χ(t) and ψ(t)
    # ------------------------------------------------------------------
    print("[10/10] Computing memory variable χ(t) (§6.3) …")
    chi = compute_chi(var_b, WINDOW_L)

    # φ(t) proxy: normalized cross-channel coherence C(t)
    phi = normalize_01(corr)

    # ------------------------------------------------------------------
    # Print summary statistics
    # ------------------------------------------------------------------
    print("\n" + "-" * 60)
    print("SUMMARY STATISTICS")
    print("-" * 60)
    print(f"  Regime (latest): {regime}")
    dpn_valid = delta_phi_norm[~np.isnan(delta_phi_norm)]
    if len(dpn_valid):
        print(f"  ΔΦ_norm  — mean={dpn_valid.mean():.3f}  max={dpn_valid.max():.3f}")
    ind_valid = indicator[~np.isnan(indicator)]
    if len(ind_valid):
        print(f"  I(t)     — mean={ind_valid.mean():.3f}  max={ind_valid.max():.3f}")
    chi_valid = chi[~np.isnan(chi)]
    if len(chi_valid):
        print(f"  χ(t)     — final={chi_valid[-1]:.4e}")
    print("-" * 60)

    return {
        "times": times,
        "X": X,
        "var_x": var_x,
        "var_b": var_b,
        "indicator": indicator,
        "delta_phi_norm": delta_phi_norm,
        "chi": chi,
        "phi": phi,
        "regime": regime,
        "flares_df": df_f,
    }


def build_figure(outputs):
    """Produce the 4-panel summary figure and save it.

    Panel 1 — X-ray flux with flare event overlay (PAPER.md §9.3, Figure 8)
    Panel 2 — Rolling variance Var_L[X](t) (§9.2, Figure 7)
    Panel 3 — ΔΦ(t) with regime bands (§6.2, §6.4, Eq. 6)
    Panel 4 — ψ(t) phase–memory trajectory φ vs χ (§7, Eq. 7)
    """
    times = outputs["times"]
    X = outputs["X"]
    var_x = outputs["var_x"]
    delta_phi_norm = outputs["delta_phi_norm"]
    chi = outputs["chi"]
    phi = outputs["phi"]
    regime = outputs["regime"]
    df_f = outputs["flares_df"]

    # Extract flare event times and class labels.
    flare_times = df_f["time_begin"].to_numpy() if "time_begin" in df_f.columns else np.array([])
    flare_classes = (
        df_f["class_type"].to_numpy() if "class_type" in df_f.columns else np.array([])
    )

    fig, axes = plt.subplots(4, 1, figsize=(14, 16))
    fig.suptitle(
        f"Solar Flare Detection — Full Pipeline Demo\n"
        f"Current regime: {regime}",
        fontsize=13,
        fontweight="bold",
    )

    # Panel 1 — X-ray flux with flare overlay
    plot_flare_overlay(times, X, flare_times, flare_classes, ax=axes[0])
    axes[0].set_title("Panel 1 — GOES X-ray Flux with Flare Events (§9.3, Fig. 8)")

    # Panel 2 — Rolling variance
    plot_rolling_variance(times, var_x, L=WINDOW_L, ax=axes[1])
    axes[1].set_title(f"Panel 2 — Rolling Variance Var_L[X](t)  L={WINDOW_L} (§9.2, Fig. 7)")

    # Panel 3 — ΔΦ(t) with regime bands
    plot_delta_phi(times, delta_phi_norm, ax=axes[2])
    axes[2].set_title("Panel 3 — Triadic Instability Operator ΔΦ(t) with Regime Bands (Eq. 6)")

    # Panel 4 — ψ(t) phase–memory trajectory
    t_numeric = np.arange(len(times), dtype=float)
    plot_psi_trajectory(phi, chi, times=t_numeric, ax=axes[3])
    axes[3].set_title("Panel 4 — Phase–Memory Trajectory ψ(t): φ(t) vs χ(t) (Eq. 7)")

    fig.tight_layout()
    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    fig.savefig(_OUTPUT_FILE, dpi=150, bbox_inches="tight")
    print(f"\nFigure saved → {_OUTPUT_FILE}")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    outputs = run_pipeline()
    build_figure(outputs)
    print("\nDone.")
