"""
math_utils.py — Shared mathematical utilities for Solar Flare Detection.

All functions implement equations from PAPER.md.  They are extracted here so
that every Python demo and future test suite can import them rather than
maintaining inline copies.

Module-level constants
----------------------
REGIME_BOUNDS  : list[float] — normalized ΔΦ threshold values (PAPER.md §6.4)
REGIME_LABELS  : list[str]   — human-readable regime names
REGIME_COLORS  : list[str]   — matplotlib-compatible hex colors for each regime
"""

import numpy as np

# ---------------------------------------------------------------------------
# Regime classification constants — PAPER.md §6.4
# ---------------------------------------------------------------------------

REGIME_BOUNDS = [0.15, 0.35, 0.40]
REGIME_LABELS = ["Isostasis", "Allostasis", "High-Allostasis", "Collapse"]
REGIME_COLORS = ["#2ecc71", "#f1c40f", "#e67e22", "#e74c3c"]


# ---------------------------------------------------------------------------
# Core math functions
# ---------------------------------------------------------------------------

def rolling_variance(series: np.ndarray, L: int) -> np.ndarray:
    """Compute rolling variance Var_L[X](t) per PAPER.md Eq. (3).

        Var_L[X](t) = (1/L) Σ_{i=0}^{L-1} (X(t-i) − X̄_L(t))²

    The first ``L-1`` values are ``NaN`` (window not yet full).

    Parameters
    ----------
    series : np.ndarray
        Input time series.
    L : int
        Window length (number of data points).

    Returns
    -------
    np.ndarray
        Rolling-variance values, same length as *series*.

    References
    ----------
    PAPER.md Eq. (3).
    """
    result = np.full_like(series, np.nan, dtype=float)
    for i in range(L - 1, len(series)):
        window = series[i - L + 1 : i + 1]
        result[i] = np.mean((window - np.mean(window)) ** 2)
    return result


def normalize_01(arr: np.ndarray) -> np.ndarray:
    """Min-max normalize *arr* to [0, 1], ignoring NaNs.

    If all values are identical the function returns an array of zeros.

    Parameters
    ----------
    arr : np.ndarray
        Input array (may contain NaN).

    Returns
    -------
    np.ndarray
        Normalized array with values in [0, 1].
    """
    lo, hi = np.nanmin(arr), np.nanmax(arr)
    if hi == lo:
        return np.zeros_like(arr)
    return (arr - lo) / (hi - lo)


def euv_derivative(euv: np.ndarray) -> np.ndarray:
    """|d/dt EUV(t)| via ``np.gradient`` (central differences at interior points).

    Parameters
    ----------
    euv : np.ndarray
        EUV irradiance time series.

    Returns
    -------
    np.ndarray
        Absolute value of the time derivative, same length as *euv*.

    References
    ----------
    PAPER.md Eq. (5) — third term |d/dt EUV(t)|.
    """
    return np.abs(np.gradient(euv))


def rolling_correlation(x: np.ndarray, y: np.ndarray, L: int) -> np.ndarray:
    """Pearson correlation of *x* and *y* over a rolling window of length *L*.

    The first ``L-1`` values are ``NaN``.  If either window has zero standard
    deviation the correlation is set to ``0.0``.

    Parameters
    ----------
    x, y : np.ndarray
        Input time series (must be the same length).
    L : int
        Window length.

    Returns
    -------
    np.ndarray
        Rolling Pearson correlation, same length as inputs.

    References
    ----------
    PAPER.md §6.2 — cross-channel coherence C(t).
    """
    result = np.full_like(x, np.nan, dtype=float)
    for i in range(L - 1, len(x)):
        wx = x[i - L + 1 : i + 1]
        wy = y[i - L + 1 : i + 1]
        if np.std(wx) > 0 and np.std(wy) > 0:
            result[i] = np.corrcoef(wx, wy)[0, 1]
        else:
            result[i] = 0.0
    return result


def classify_regime(delta_phi_norm: float) -> str:
    """Map a normalized ΔΦ value to a regime label (PAPER.md §6.4).

    Thresholds (applied after normalization to [0, 1]):

    ==================  =====================================
    ΔΦ range            Regime
    ==================  =====================================
    ΔΦ < 0.15           Isostasis
    0.15 ≤ ΔΦ < 0.35    Allostasis
    0.35 ≤ ΔΦ < 0.40    High-Allostasis
    ΔΦ ≥ 0.40           Collapse
    ==================  =====================================

    Parameters
    ----------
    delta_phi_norm : float
        Normalized ΔΦ value in [0, 1].

    Returns
    -------
    str
        One of ``"Isostasis"``, ``"Allostasis"``, ``"High-Allostasis"``,
        ``"Collapse"``.

    References
    ----------
    PAPER.md §6.4.
    """
    if delta_phi_norm < 0.15:
        return "Isostasis"
    if delta_phi_norm < 0.35:
        return "Allostasis"
    if delta_phi_norm < 0.40:
        return "High-Allostasis"
    return "Collapse"


def compute_delta_phi(
    S: np.ndarray,
    I: np.ndarray,
    C: np.ndarray,
    alpha: float = 1 / 3,
    beta: float = 1 / 3,
    gamma: float = 1 / 3,
) -> np.ndarray:
    """Triadic instability operator ΔΦ(t) — PAPER.md Eq. (6).

        ΔΦ(t) = α |ΔS(t)| + β |ΔI(t)| + γ |ΔC(t)|

    First differences are computed via ``np.diff`` with ``prepend=np.nan`` so
    the output has the same length as the inputs and the first element is
    ``NaN``.

    Parameters
    ----------
    S : np.ndarray
        Structural variability S(t) (e.g. ``rolling_variance(B, L)``).
    I : np.ndarray
        Informational complexity I(t) (e.g. ``rolling_variance(X, L)``).
    C : np.ndarray
        Cross-channel coherence C(t) (e.g. ``rolling_correlation(X, EUV, L)``).
    alpha, beta, gamma : float
        Weighting coefficients; default 1/3 each (equal weighting).

    Returns
    -------
    np.ndarray
        ΔΦ(t) values, same length as inputs. First element is ``NaN``.

    References
    ----------
    PAPER.md Eq. (6).
    """
    dS = np.abs(np.diff(S, prepend=np.nan))
    dI = np.abs(np.diff(I, prepend=np.nan))
    dC = np.abs(np.diff(C, prepend=np.nan))
    return alpha * dS + beta * dI + gamma * dC


def compute_composite_indicator(
    var_x_norm: np.ndarray,
    var_b_norm: np.ndarray,
    d_euv_norm: np.ndarray,
    w1: float = 1 / 3,
    w2: float = 1 / 3,
    w3: float = 1 / 3,
) -> np.ndarray:
    """Composite instability indicator I(t) — PAPER.md Eq. (5).

        I(t) = w₁ Var_L[X](t) + w₂ Var_L[B](t) + w₃ |d/dt EUV(t)|

    All three input components must already be normalized to [0, 1] so that
    equal weights are physically meaningful.

    Parameters
    ----------
    var_x_norm : np.ndarray
        Rolling variance of X-ray flux, normalized to [0, 1].
    var_b_norm : np.ndarray
        Rolling variance of magnetometer B(t), normalized to [0, 1].
    d_euv_norm : np.ndarray
        Absolute EUV time-derivative, normalized to [0, 1].
    w1, w2, w3 : float
        Weighting coefficients; default 1/3 each (equal weighting).

    Returns
    -------
    np.ndarray
        Composite indicator I(t) values, same length as inputs.

    References
    ----------
    PAPER.md Eq. (5).
    """
    return w1 * var_x_norm + w2 * var_b_norm + w3 * d_euv_norm


def compute_chi(var_b: np.ndarray, window_L: int) -> np.ndarray:
    """Compute memory variable χ(t) as cumulative integral of Var_L[B](t).

    Uses ``numpy.cumsum`` as a trapezoidal approximation.  NaN values in the
    pre-window region (first ``window_L - 1`` entries) are preserved.

        χ(t) ≈ ∫₀ᵗ Var_L[B](τ) dτ

    Parameters
    ----------
    var_b : np.ndarray
        Rolling variance of magnetometer B(t).
    window_L : int
        Window length used to produce *var_b* (controls NaN masking).

    Returns
    -------
    np.ndarray
        χ(t) values (cumulative integral), same length as *var_b*.

    References
    ----------
    PAPER.md §6.3 — memory variable χ(t).
    """
    integrand = np.where(np.isnan(var_b), 0.0, var_b)
    chi = np.cumsum(integrand)
    chi[: window_L - 1] = np.nan
    return chi
