"""
synthetic_pipeline_numbers.py — Synthetic GOES-like data pipeline for PAPER.md.

Generates a fully synthetic 7-day dataset (N=10 000, seed=42) and computes
every metric defined in PAPER.md.  Prints concrete numerical outputs to stdout
in table form and saves five figures to output/synthetic_pipeline/.

Scientific pipeline
-------------------
All equations refer to Krüger & Feeney (2026), PAPER.md.

1.  Generate synthetic X(t), B(t), EUV(t) with flare-like spikes
2.  Rolling variance Var_L[X] and Var_L[B]  (Eq. 3, L=200)
3.  EUV derivative |d/dt EUV(t)|            (Eq. 5 — third term)
4.  Normalize all components to [0, 1]
5.  Composite indicator I(t)                (Eq. 5, w1=0.5, w2=0.3, w3=0.2)
6.  Rolling correlation C(t)               (§6.2, L=200)
7.  Triadic instability operator ΔΦ(t)     (Eq. 6, α=0.4, β=0.4, γ=0.2)
8.  Regime classification                  (§6.4)
9.  Memory variable χ(t)                   (§6.3, L=200)
10. Phase–memory embedding ψ(t) = (φ, χ)

Usage
-----
    python domains/spiral_time/examples_python/synthetic_pipeline_numbers.py

Output figures saved to:
    output/synthetic_pipeline/
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

from shared.math_utils import (
    rolling_variance,
    normalize_01,
    euv_derivative,
    rolling_correlation,
    compute_composite_indicator,
    compute_delta_phi,
    classify_regime,
    compute_chi,
    REGIME_LABELS,
    REGIME_BOUNDS,
)
from shared.plot_utils import (
    plot_flare_overlay,
    plot_rolling_variance,
    plot_delta_phi,
    plot_psi_trajectory,
    plot_composite_indicator,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

N = 10_000                          # number of time steps
WINDOW_L = 200                      # rolling-window length L
W1, W2, W3 = 0.5, 0.3, 0.2         # composite indicator weights
ALPHA, BETA, GAMMA = 0.4, 0.4, 0.2  # triadic operator weights

QUIET_SUN_BASELINE = 1e-7   # W m⁻²; quiet-sun X-ray flux level
FLARE_SPIKE_WIDTH = 150     # samples; Gaussian half-width for synthetic flares

_OUTPUT_DIR = os.path.join(_REPO_ROOT, "output", "synthetic_pipeline")


# ---------------------------------------------------------------------------
# Step 1 — Generate synthetic dataset
# ---------------------------------------------------------------------------

def generate_synthetic_data():
    """Return synthetic time series (times, X, B, EUV, flare_times, flare_classes).

    Parameters
    ----------
    None

    Returns
    -------
    times        : np.ndarray, shape (N,)  — uniform 7-day grid (seconds)
    X            : np.ndarray, shape (N,)  — X-ray flux proxy
    B            : np.ndarray, shape (N,)  — magnetic proxy
    EUV          : np.ndarray, shape (N,)  — EUV irradiance proxy
    flare_times  : list[int]               — indices of synthetic flare peaks
    flare_classes: list[str]               — GOES class labels ("C", "M")
    """
    rng = np.random.default_rng(42)

    # Uniform time grid: 7 days at N points (~60.48-second cadence)
    duration_s = 7 * 24 * 3600  # 7 days in seconds
    times = np.linspace(0, duration_s, N)

    # --- X(t): smooth baseline + Gaussian noise + 2 flare spikes ---
    baseline_x = QUIET_SUN_BASELINE * np.ones(N)
    noise_x = rng.normal(0, 1e-8, N)
    X = baseline_x + noise_x

    # Flare spikes at ~25 % and ~70 % of the time series
    flare_idx = [int(0.25 * N), int(0.70 * N)]
    flare_classes = ["C", "M"]
    flare_amplitudes = [8e-7, 1.5e-6]   # 8× and 15× baseline

    for idx, amp in zip(flare_idx, flare_amplitudes):
        gauss = amp * np.exp(-0.5 * ((np.arange(N) - idx) / FLARE_SPIKE_WIDTH) ** 2)
        X = X + gauss

    # Ensure positivity
    X = np.clip(X, 1e-10, None)

    # --- B(t): correlated with X, noisier ---
    B = 0.6 * (X / X.max()) + 0.4 * rng.normal(0.5, 0.15, N)
    B = np.clip(B, 1e-6, None)

    # --- EUV(t): slow drift + small fluctuations ---
    slow_drift = 0.1 * np.sin(2 * np.pi * times / (3 * 24 * 3600))  # 3-day period
    EUV = 1.0 + slow_drift + rng.normal(0, 0.02, N)
    EUV = np.clip(EUV, 0.01, None)

    flare_times = [times[i] for i in flare_idx]
    return times, X, B, EUV, flare_times, flare_classes


# ---------------------------------------------------------------------------
# Step 2–10 — Compute all PAPER.md metrics
# ---------------------------------------------------------------------------

def compute_metrics(times, X, B, EUV):
    """Compute every metric defined in PAPER.md and return them as a dict."""

    # Rolling variance (Eq. 3)
    var_x = rolling_variance(X, WINDOW_L)
    var_b = rolling_variance(B, WINDOW_L)

    # EUV derivative (Eq. 5 — third term)
    d_euv = euv_derivative(EUV)

    # Normalize to [0, 1]
    var_x_norm = normalize_01(var_x)
    var_b_norm = normalize_01(var_b)
    d_euv_norm = normalize_01(d_euv)

    # Composite indicator I(t) (Eq. 5)
    indicator = compute_composite_indicator(
        var_x_norm, var_b_norm, d_euv_norm, w1=W1, w2=W2, w3=W3
    )

    # Rolling correlation C(t) (§6.2)
    corr = rolling_correlation(X, EUV, WINDOW_L)

    # Triadic instability operator ΔΦ(t) (Eq. 6)
    delta_phi = compute_delta_phi(var_b, var_x, corr, ALPHA, BETA, GAMMA)
    delta_phi_norm = normalize_01(delta_phi)

    # Memory variable χ(t) (§6.3)
    chi = compute_chi(var_b, WINDOW_L)

    # Phase–memory embedding φ = normalized rolling correlation
    phi = normalize_01(corr)

    return {
        "var_x": var_x,
        "var_b": var_b,
        "d_euv": d_euv,
        "var_x_norm": var_x_norm,
        "var_b_norm": var_b_norm,
        "d_euv_norm": d_euv_norm,
        "indicator": indicator,
        "corr": corr,
        "delta_phi_norm": delta_phi_norm,
        "chi": chi,
        "phi": phi,
    }


# ---------------------------------------------------------------------------
# Step 3 — Print concrete numerical outputs
# ---------------------------------------------------------------------------

def _stats(arr, label):
    """Return (mean, median, std) ignoring NaNs and print a table row."""
    valid = arr[~np.isnan(arr)]
    m, med, s = float(np.mean(valid)), float(np.median(valid)), float(np.std(valid))
    print(f"  {label:<30s}  mean={m:.6e}  median={med:.6e}  std={s:.6e}")
    return m, med, s


def print_outputs(times, metrics, flare_times, flare_classes):
    """Print all required table outputs to stdout."""

    var_x = metrics["var_x"]
    var_b = metrics["var_b"]
    d_euv = metrics["d_euv"]
    indicator = metrics["indicator"]
    delta_phi_norm = metrics["delta_phi_norm"]
    chi = metrics["chi"]
    phi = metrics["phi"]

    print()
    print("=" * 70)
    print("SYNTHETIC PIPELINE NUMBERS  (seed=42, N=10 000, L=200)")
    print("=" * 70)

    # --- Table 1: Rolling variance & derivative statistics ---
    print()
    print("Table 1 — Rolling variance and EUV derivative statistics")
    print("-" * 70)
    vx_stats = _stats(var_x, "Var_L[X]")
    vb_stats = _stats(var_b, "Var_L[B]")
    de_stats = _stats(d_euv, "dEUV/dt")

    # --- Table 2: Composite indicator statistics ---
    print()
    print("Table 2 — Composite indicator I(t)  (w1=0.5, w2=0.3, w3=0.2)")
    print("-" * 70)
    in_stats = _stats(indicator, "I(t)")

    # --- Table 3: ΔΦ(t) distribution ---
    valid_dpn = delta_phi_norm[~np.isnan(delta_phi_norm)]
    print()
    print("Table 3 — Triadic instability operator ΔΦ(t) distribution")
    print("-" * 70)
    print(f"  min    = {float(np.nanmin(delta_phi_norm)):.6f}")
    print(f"  Q1     = {float(np.nanpercentile(delta_phi_norm, 25)):.6f}")
    print(f"  median = {float(np.nanmedian(delta_phi_norm)):.6f}")
    print(f"  Q3     = {float(np.nanpercentile(delta_phi_norm, 75)):.6f}")
    print(f"  max    = {float(np.nanmax(delta_phi_norm)):.6f}")

    # --- Table 4: Regime counts ---
    print()
    print("Table 4 — Regime classification counts  (PAPER.md §6.4)")
    print("-" * 70)
    regime_counts = {label: 0 for label in REGIME_LABELS}
    for v in valid_dpn:
        regime_counts[classify_regime(float(v))] += 1
    for label in REGIME_LABELS:
        print(f"  {label:<20s}  {regime_counts[label]:>6d}")

    # --- Table 5: χ(t) monotonicity ---
    valid_chi = chi[~np.isnan(chi)]
    is_monotone = bool(np.all(np.diff(valid_chi) >= 0))
    print()
    print("Table 5 — Memory variable χ(t) monotonicity check")
    print("-" * 70)
    print(f"  χ(t) non-decreasing (monotone):  {is_monotone}")

    # --- Table 6: ψ(t) sample points ---
    valid_mask = ~(np.isnan(phi) | np.isnan(chi))
    valid_phi = phi[valid_mask]
    valid_chi_arr = chi[valid_mask]
    valid_times = times[valid_mask]
    n_valid = len(valid_phi)
    indices = np.linspace(0, n_valid - 1, 10, dtype=int)
    print()
    print("Table 6 — Phase–memory embedding ψ(t): 10 representative (φ, χ) pairs")
    print("-" * 70)
    print(f"  {'Index':>7s}  {'Time (s)':>14s}  {'φ(t)':>10s}  {'χ(t)':>14s}")
    for idx in indices:
        print(
            f"  {idx:>7d}  {valid_times[idx]:>14.1f}"
            f"  {valid_phi[idx]:>10.6f}  {valid_chi_arr[idx]:>14.6e}"
        )

    print()
    print("=" * 70)

    return {
        "vx_stats": vx_stats,
        "vb_stats": vb_stats,
        "de_stats": de_stats,
        "in_stats": in_stats,
        "dpn_min": float(np.nanmin(delta_phi_norm)),
        "dpn_q1": float(np.nanpercentile(delta_phi_norm, 25)),
        "dpn_median": float(np.nanmedian(delta_phi_norm)),
        "dpn_q3": float(np.nanpercentile(delta_phi_norm, 75)),
        "dpn_max": float(np.nanmax(delta_phi_norm)),
        "regime_counts": regime_counts,
        "is_monotone": is_monotone,
        "psi_pairs": list(
            zip(valid_phi[indices].tolist(), valid_chi_arr[indices].tolist())
        ),
        "psi_indices": indices.tolist(),
        "psi_times": valid_times[indices].tolist(),
    }


# ---------------------------------------------------------------------------
# Step 4 — Save figures
# ---------------------------------------------------------------------------

def save_figures(times, X, metrics, flare_times, flare_classes):
    """Save five diagnostic figures to output/synthetic_pipeline/."""

    os.makedirs(_OUTPUT_DIR, exist_ok=True)

    var_x = metrics["var_x"]
    delta_phi_norm = metrics["delta_phi_norm"]
    chi = metrics["chi"]
    phi = metrics["phi"]
    indicator = metrics["indicator"]

    # Figure 1 — X-ray flux with flare overlay
    fig, ax = plot_flare_overlay(
        times, X, flare_times, flare_classes, label="Synthetic X(t)"
    )
    ax.set_title("Synthetic X-ray Flux with Flare Overlay")
    path1 = os.path.join(_OUTPUT_DIR, "xray_flux_flare_overlay.png")
    fig.savefig(path1, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved → {path1}")

    # Figure 2 — Rolling variance Var_L[X]
    fig, ax = plot_rolling_variance(times, var_x, L=WINDOW_L)
    ax.set_title(f"Rolling Variance Var_L[X](t)  L={WINDOW_L}")
    path2 = os.path.join(_OUTPUT_DIR, "rolling_variance_x.png")
    fig.savefig(path2, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved → {path2}")

    # Figure 3 — ΔΦ(t) with regime bands
    fig, ax = plot_delta_phi(times, delta_phi_norm)
    ax.set_title("Triadic Instability Operator ΔΦ(t) with Regime Bands")
    path3 = os.path.join(_OUTPUT_DIR, "delta_phi_regime_bands.png")
    fig.savefig(path3, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved → {path3}")

    # Figure 4 — ψ-trajectory (phi vs chi)
    t_numeric = np.arange(N, dtype=float)
    fig, ax = plot_psi_trajectory(phi, chi, times=t_numeric)
    ax.set_title("Phase–Memory Trajectory ψ(t): φ(t) vs χ(t)")
    path4 = os.path.join(_OUTPUT_DIR, "psi_trajectory.png")
    fig.savefig(path4, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved → {path4}")

    # Figure 5 — Composite indicator I(t)
    fig, ax = plot_composite_indicator(times, indicator)
    ax.set_title("Composite Instability Indicator I(t)")
    path5 = os.path.join(_OUTPUT_DIR, "composite_indicator.png")
    fig.savefig(path5, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved → {path5}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Generating synthetic 7-day GOES-like dataset  (N=10 000, seed=42) …")
    times, X, B, EUV, flare_times, flare_classes = generate_synthetic_data()
    print(f"  times  : {times[0]:.1f} – {times[-1]:.1f} s  (cadence ≈ {times[1]-times[0]:.2f} s)")
    print(f"  X(t)   : min={X.min():.3e}  max={X.max():.3e}")
    print(f"  B(t)   : min={B.min():.3e}  max={B.max():.3e}")
    print(f"  EUV(t) : min={EUV.min():.3e}  max={EUV.max():.3e}")
    print(f"  Flare events: {len(flare_times)} × {flare_classes}")

    print("\nComputing all PAPER.md metrics …")
    metrics = compute_metrics(times, X, B, EUV)

    table_data = print_outputs(times, metrics, flare_times, flare_classes)

    print("\nSaving figures …")
    save_figures(times, X, metrics, flare_times, flare_classes)

    print("\nDone.")
