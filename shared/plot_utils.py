"""
plot_utils.py — Shared visualization utilities for Solar Flare Detection.

Provides reusable plotting functions that implement the figure patterns
described in PAPER.md §9 (Figures 6–8) and §6.4.  All functions:

- Accept pre-computed numpy arrays (no data loading).
- Return ``(fig, ax)`` tuples (or modify an existing ``ax``) for composability.
- Apply consistent Solar Flare Detection plot styling.

Module-level constants
----------------------
FLARE_CLASS_COLORS : dict — flare class letter → matplotlib hex color
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from shared.math_utils import REGIME_BOUNDS, REGIME_COLORS, REGIME_LABELS

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Flare class → color mapping used in Figures 6–8 (PAPER.md §9.3 convention).
FLARE_CLASS_COLORS: dict = {
    "X": "#e74c3c",   # red
    "M": "#e67e22",   # orange
    "C": "#f1c40f",   # yellow
    "B": "#95a5a6",   # gray
    "A": "#bdc3c7",   # light gray
}

#: Fallback color for unknown flare class letters.
_UNKNOWN_FLARE_COLOR: str = "#7f8c8d"


# ---------------------------------------------------------------------------
# Styling helper
# ---------------------------------------------------------------------------

def style_solar_axes(ax, title: str = None, ylabel: str = None) -> None:
    """Apply consistent Solar Flare Detection plot styling to *ax*.

    Sets grid, font sizes, optional title and y-axis label, and configures
    auto-formatted datetime x-axis labels.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        Target axes to style.
    title : str, optional
        Axes title text.
    ylabel : str, optional
        Y-axis label text.
    """
    ax.grid(True, alpha=0.3)
    ax.tick_params(labelsize=9)
    if title is not None:
        ax.set_title(title, fontsize=11)
    if ylabel is not None:
        ax.set_ylabel(ylabel, fontsize=10)
    # Auto-format datetime x-axis if the data looks like datetime objects
    try:
        ax.figure.autofmt_xdate(rotation=30, ha="right")
        ax.xaxis.set_major_formatter(mdates.AutoDateFormatter(mdates.AutoDateLocator()))
    except (TypeError, AttributeError):
        pass


# ---------------------------------------------------------------------------
# Core plotting functions
# ---------------------------------------------------------------------------

def plot_xray_flux(times, flux: np.ndarray, ax=None, **kwargs):
    """Plot X-ray flux on a log-scale Y axis — PAPER.md §9.1, Figure 6.

    Parameters
    ----------
    times : array-like
        Time values for the x-axis (datetime-compatible or numeric).
    flux : np.ndarray
        X-ray flux values (W m⁻²).
    ax : matplotlib.axes.Axes, optional
        Existing axes to draw on.  A new figure is created if *None*.
    **kwargs
        Extra keyword arguments forwarded to ``ax.semilogy``.

    Returns
    -------
    fig : matplotlib.figure.Figure
    ax : matplotlib.axes.Axes
    """
    if ax is None:
        fig, ax = plt.subplots(figsize=(12, 4))
    else:
        fig = ax.figure

    plot_kw = dict(color="#2980b9", linewidth=0.7, label="X-ray flux X(t)")
    plot_kw.update(kwargs)
    ax.semilogy(times, flux, **plot_kw)

    style_solar_axes(ax, ylabel="Flux (W m⁻²)")
    ax.set_xlabel("Time", fontsize=10)
    return fig, ax


def plot_rolling_variance(times, variance: np.ndarray, L: int, ax=None, **kwargs):
    """Plot rolling variance evolution — PAPER.md §9.2, Figure 7.

    Parameters
    ----------
    times : array-like
        Time values for the x-axis.
    variance : np.ndarray
        Rolling-variance values (same length as *times*).
    L : int
        Window length used to compute *variance*; included in the axis label.
    ax : matplotlib.axes.Axes, optional
        Existing axes to draw on.  A new figure is created if *None*.
    **kwargs
        Extra keyword arguments forwarded to ``ax.plot``.

    Returns
    -------
    fig : matplotlib.figure.Figure
    ax : matplotlib.axes.Axes
    """
    if ax is None:
        fig, ax = plt.subplots(figsize=(12, 4))
    else:
        fig = ax.figure

    plot_kw = dict(color="#e67e22", linewidth=0.7, label=f"Var_L[X](t)  L={L}")
    plot_kw.update(kwargs)
    ax.plot(times, variance, **plot_kw)

    style_solar_axes(ax, ylabel=f"Var_L[X](t)  (L={L})")
    ax.set_xlabel("Time", fontsize=10)
    return fig, ax


def plot_flare_overlay(
    times,
    flux: np.ndarray,
    flare_times,
    flare_classes,
    ax=None,
    **kwargs,
):
    """Plot X-ray flux with flare event vertical lines — PAPER.md §9.3, Figure 8.

    Each flare event at time *tₖ* is drawn as a vertical line colour-coded by
    its GOES class using ``FLARE_CLASS_COLORS``.

    Parameters
    ----------
    times : array-like
        Time values for the x-axis.
    flux : np.ndarray
        X-ray flux values (W m⁻²).
    flare_times : array-like
        Timestamp for each flare event.
    flare_classes : array-like
        GOES flare class letter (``"X"``, ``"M"``, ``"C"``, ``"B"``, ``"A"``)
        for each event in *flare_times*.
    ax : matplotlib.axes.Axes, optional
        Existing axes to draw on.  A new figure is created if *None*.
    **kwargs
        Extra keyword arguments forwarded to ``ax.semilogy``.

    Returns
    -------
    fig : matplotlib.figure.Figure
    ax : matplotlib.axes.Axes
    """
    if ax is None:
        fig, ax = plt.subplots(figsize=(12, 4))
    else:
        fig = ax.figure

    plot_kw = dict(color="#2980b9", linewidth=0.7, label="X-ray flux X(t)")
    plot_kw.update(kwargs)
    ax.semilogy(times, flux, **plot_kw)

    for t, cls in zip(flare_times, flare_classes):
        color = FLARE_CLASS_COLORS.get(str(cls).upper(), _UNKNOWN_FLARE_COLOR)
        ax.axvline(t, color=color, linewidth=0.8, alpha=0.7)

    style_solar_axes(ax, ylabel="Flux (W m⁻²)")
    ax.set_xlabel("Time", fontsize=10)
    return fig, ax


def plot_delta_phi(times, delta_phi_norm: np.ndarray, ax=None, **kwargs):
    """Plot normalized ΔΦ(t) with regime bands — PAPER.md §6.2, §6.4, Eq. (6).

    Draws the triadic instability operator ΔΦ(t) as a line plot on the [0, 1]
    y-axis, automatically overlays the four regime bands via
    ``add_regime_bands()``, and applies ``style_solar_axes()`` for consistent
    styling.

    Parameters
    ----------
    times : array-like
        Time values for the x-axis (datetime-compatible or numeric).
    delta_phi_norm : np.ndarray
        Normalized ΔΦ(t) values in [0, 1].
    ax : matplotlib.axes.Axes, optional
        Existing axes to draw on.  A new figure is created if *None*.
    **kwargs
        Extra keyword arguments forwarded to ``ax.plot``.

    Returns
    -------
    fig : matplotlib.figure.Figure
    ax : matplotlib.axes.Axes

    References
    ----------
    PAPER.md §6.2, §6.4, Eq. (6).
    """
    if ax is None:
        fig, ax = plt.subplots(figsize=(12, 4))
    else:
        fig = ax.figure

    add_regime_bands(ax, delta_phi_norm, times)

    plot_kw = dict(color="#8e44ad", linewidth=0.9, label="ΔΦ(t) — normalized")
    plot_kw.update(kwargs)
    ax.plot(times, delta_phi_norm, **plot_kw)
    ax.set_ylim(0, 1)

    style_solar_axes(ax, ylabel="ΔΦ(t) — normalized")
    ax.set_xlabel("Time", fontsize=10)
    return fig, ax


def plot_psi_trajectory(phi: np.ndarray, chi: np.ndarray, times=None, ax=None, **kwargs):
    """Plot the phase–memory trajectory φ(t) vs χ(t) — PAPER.md §7, §10.1, Eq. (7).

    Draws the 2D phase–memory embedding ψ(t) = t + iφ(t) + jχ(t) as a scatter
    or line plot of φ(t) on the x-axis versus χ(t) on the y-axis.  When
    *times* is provided the points are colour-coded by time using the
    ``"plasma"`` colormap.

    Parameters
    ----------
    phi : np.ndarray
        Phase coherence coordinate φ(t) — e.g. ``normalize_01(rolling_correlation(...))``.
    chi : np.ndarray
        Memory coordinate χ(t) — e.g. ``compute_chi(var_b, L)``.
    times : array-like, optional
        Time values used to colour-code the trajectory.  If *None*, a uniform
        blue line is drawn instead.
    ax : matplotlib.axes.Axes, optional
        Existing axes to draw on.  A new figure is created if *None*.
    **kwargs
        Extra keyword arguments forwarded to ``ax.scatter`` (when *times* is
        provided) or ``ax.plot`` (when *times* is *None*).

    Returns
    -------
    fig : matplotlib.figure.Figure
    ax : matplotlib.axes.Axes

    References
    ----------
    PAPER.md §7, §10.1, Eq. (7).
    """
    if ax is None:
        fig, ax = plt.subplots(figsize=(6, 6))
    else:
        fig = ax.figure

    if times is not None:
        t_numeric = np.asarray(times, dtype=float)
        t_norm = (t_numeric - np.nanmin(t_numeric)) / max(
            np.nanmax(t_numeric) - np.nanmin(t_numeric), 1e-12
        )
        scatter_kw = dict(c=t_norm, cmap="plasma", s=8, alpha=0.7)
        scatter_kw.update(kwargs)
        sc = ax.scatter(phi, chi, **scatter_kw)
        fig.colorbar(sc, ax=ax, label="Time (normalized)")
    else:
        plot_kw = dict(color="#2980b9", linewidth=0.8, alpha=0.8)
        plot_kw.update(kwargs)
        ax.plot(phi, chi, **plot_kw)

    style_solar_axes(ax, ylabel="χ(t) — Memory")
    ax.set_xlabel("φ(t) — Phase Coherence", fontsize=10)
    return fig, ax


def plot_composite_indicator(times, indicator: np.ndarray, ax=None, **kwargs):
    """Plot the composite instability indicator I(t) — PAPER.md §6.1, Eq. (5).

    Parameters
    ----------
    times : array-like
        Time values for the x-axis (datetime-compatible or numeric).
    indicator : np.ndarray
        Composite indicator I(t) values (should be in [0, 1] after
        normalization).
    ax : matplotlib.axes.Axes, optional
        Existing axes to draw on.  A new figure is created if *None*.
    **kwargs
        Extra keyword arguments forwarded to ``ax.plot``.

    Returns
    -------
    fig : matplotlib.figure.Figure
    ax : matplotlib.axes.Axes

    References
    ----------
    PAPER.md §6.1, Eq. (5).
    """
    if ax is None:
        fig, ax = plt.subplots(figsize=(12, 4))
    else:
        fig = ax.figure

    plot_kw = dict(color="#27ae60", linewidth=0.9, label="I(t) — Composite Indicator")
    plot_kw.update(kwargs)
    ax.plot(times, indicator, **plot_kw)

    style_solar_axes(ax, ylabel="I(t) — Composite Indicator")
    ax.set_xlabel("Time", fontsize=10)
    return fig, ax


def add_regime_bands(ax, delta_phi_norm: np.ndarray, times) -> None:
    """Add colored horizontal bands for the four regimes to *ax*.

    Uses ``REGIME_BOUNDS``, ``REGIME_COLORS``, and ``REGIME_LABELS`` from
    ``shared.math_utils`` to draw ``axhspan`` overlays, providing visual
    context for ΔΦ regime classification.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        Axes containing a ΔΦ plot.  The bands are added as horizontal spans.
    delta_phi_norm : np.ndarray
        Normalized ΔΦ values (used only to determine the y-axis extent for
        labelling purposes; the spans cover fixed threshold ranges).
    times : array-like
        Time values (unused by this function; included for API consistency with
        the other helpers in this module).

    References
    ----------
    PAPER.md §6.4 — regime thresholds.
    """
    # Build boundary pairs: [0, b0], [b0, b1], [b1, b2], [b2, ∞)
    bounds = [0.0] + list(REGIME_BOUNDS) + [float("inf")]
    for i, (lo, hi, color, label) in enumerate(
        zip(bounds[:-1], bounds[1:], REGIME_COLORS, REGIME_LABELS)
    ):
        # Cap the upper bound for the infinite region at 1.0 for display
        hi_display = min(hi, 1.0)
        ax.axhspan(lo, hi_display, color=color, alpha=0.15, label=label)
