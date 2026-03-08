"""
domains/spiral_time/examples_python/make_goes_summary_report.py
================================================================
Loads real GOES 7-day observational data, produces three numeric CSV tables,
three publication-ready PNG figures (300 dpi), and assembles a single PDF
summary report.

Figures produced
----------------
Figure 6  fig6_goes_xray_flux.png        — GOES 0.1–0.8 nm semilog time series
Figure 7  fig7_windowed_variance.png     — Rolling/windowed variance (L=200)
Figure 8  fig8_flare_event_overlay.png   — Flux time series with flare markers

CSV tables produced
-------------------
goes_table_a_flux.csv            — time_utc | xray_flux
goes_table_b_rolling_variance.csv — time_utc | rolling_variance | window_L
goes_table_c_flare_overlay.csv   — time_utc | xray_flux | flare_flag | flare_class

PDF report
----------
goes_summary_report.pdf

All outputs are written to:
    output/paper_figures/   (created automatically if absent)

Usage
-----
    python domains/spiral_time/examples_python/make_goes_summary_report.py

Dependencies: numpy, matplotlib, pandas (see requirements.txt)
"""

import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.image import imread
import pandas as pd

# ---------------------------------------------------------------------------
# Ensure repo root is on sys.path regardless of working directory.
# ---------------------------------------------------------------------------

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

# Maximum rows to display per table in the PDF (for readability).
_PDF_TABLE_ROWS = 30


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_flux():
    """Load GOES 0.1–0.8 nm X-ray flux; return (times, flux) arrays.

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


def _is_valid_time(t):
    """Return True if *t* is a usable (non-None, non-NaT) timestamp."""
    if t is None:
        return False
    try:
        return not pd.isna(t)
    except (TypeError, ValueError):
        return True


def _load_flares():
    """Load NOAA flare catalogue; return list of (onset_time, flare_class).

    Uses ``begin_time`` as the flare onset when available; falls back to
    ``time_max`` for records where ``begin_time`` is None or NaT.
    ``flare_class`` is the full NOAA designator (e.g. 'M2.3') or '' when
    unavailable.

    Returns
    -------
    list[tuple[datetime, str]]
        (onset_time, flare_class) pairs, sorted by onset_time.
    """
    df = load_xray_flares()
    flare_data = []
    for _, row in df.iterrows():
        time_begin = row["time_begin"]
        time_max = row["time_max"]
        onset = time_begin if _is_valid_time(time_begin) else time_max
        if not _is_valid_time(onset):
            continue
        class_type = row["class_type"] if row["class_type"] else ""
        class_num = row["class_num"]
        if class_type and not pd.isna(class_num):
            flare_class = f"{class_type}{class_num:g}"
        else:
            flare_class = class_type
        flare_data.append((onset, flare_class))
    return flare_data


# ---------------------------------------------------------------------------
# Figure helpers (mirroring make_goes_figures.py)
# ---------------------------------------------------------------------------

def _apply_utc_xaxis(ax):
    """Format x-axis as UTC dates with the required tick-label format."""
    ax.xaxis.set_major_formatter(mdates.DateFormatter(_TIME_FMT))
    ax.figure.autofmt_xdate(rotation=0, ha="center")


def make_fig6(times, flux):
    """Figure 6: semilog GOES 0.1–0.8 nm X-ray flux time series.

    Parameters
    ----------
    times : list[datetime]
    flux : np.ndarray

    Returns
    -------
    str
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


def make_fig7(times, var):
    """Figure 7: rolling variance of X-ray flux with window length L=200.

    Parameters
    ----------
    times : list[datetime]
    var : np.ndarray
        Pre-computed rolling variance array (NaN for first L-1 entries).

    Returns
    -------
    str
        Absolute path of the saved PNG.
    """
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


def make_fig8(times, flux, flare_data):
    """Figure 8: semilog X-ray flux with vertical lines at flare onsets.

    Parameters
    ----------
    times : list[datetime]
    flux : np.ndarray
    flare_data : list[tuple[datetime, str]]
        (onset_time, flare_class) pairs.

    Returns
    -------
    str
        Absolute path of the saved PNG.
    """
    flare_times = [flare_time for flare_time, _ in flare_data]

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
# Table construction
# ---------------------------------------------------------------------------

def _fmt_times(times):
    """Convert a list of datetimes to ISO-8601 UTC strings."""
    return [
        t.strftime("%Y-%m-%dT%H:%M:%SZ") if _is_valid_time(t) else ""
        for t in times
    ]


def build_table_a(times, flux):
    """Table A — Flux (Figure 6).

    Columns: time_utc | xray_flux
    """
    return pd.DataFrame({
        "time_utc": _fmt_times(times),
        "xray_flux": flux,
    })


def build_table_b(times, var):
    """Table B — Rolling Variance (Figure 7).

    Columns: time_utc | rolling_variance | window_L
    NaN is stored for the first L-1 entries (warm-up period).
    """
    return pd.DataFrame({
        "time_utc": _fmt_times(times),
        "rolling_variance": var,
        "window_L": WINDOW_L,
    })


def build_table_c(times, flux, flare_data):
    """Table C — Flare Overlay (Figure 8).

    Columns: time_utc | xray_flux | flare_flag | flare_class

    flare_flag = 1 when a flare onset coincides (to the minute) with the
    flux timestamp; 0 otherwise.  flare_class is the NOAA designator or ''.
    """
    # Map flare onset times (truncated to the minute) to their class strings.
    onset_map = {}
    for onset, flare_class in flare_data:
        key = onset.replace(second=0, microsecond=0)
        onset_map[key] = flare_class

    flare_flags = []
    flare_classes = []
    for t in times:
        if not _is_valid_time(t):
            flare_flags.append(0)
            flare_classes.append("")
            continue
        key = t.replace(second=0, microsecond=0)
        if key in onset_map:
            flare_flags.append(1)
            flare_classes.append(onset_map[key])
        else:
            flare_flags.append(0)
            flare_classes.append("")

    return pd.DataFrame({
        "time_utc": _fmt_times(times),
        "xray_flux": flux,
        "flare_flag": flare_flags,
        "flare_class": flare_classes,
    })


# ---------------------------------------------------------------------------
# PDF helpers
# ---------------------------------------------------------------------------

def _render_df_table(ax, df, max_rows=_PDF_TABLE_ROWS):
    """Render a representative sample of *df* as a table on *ax*."""
    ax.axis("off")
    n_total = len(df)
    if n_total > max_rows:
        step = max(1, n_total // max_rows)
        sample = df.iloc[::step].head(max_rows)
        subtitle = f"(showing every {step}-th row; {n_total} rows total)"
    else:
        sample = df
        subtitle = f"({n_total} rows)"

    ax.set_title(subtitle, fontsize=7, loc="left", pad=4)

    col_labels = list(sample.columns)
    cell_text = [[str(v) for v in row] for _, row in sample.iterrows()]

    tbl = ax.table(
        cellText=cell_text,
        colLabels=col_labels,
        loc="center",
        cellLoc="left",
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(6)
    tbl.auto_set_column_width(list(range(len(col_labels))))


def make_pdf_report(times, fig6_path, fig7_path, fig8_path,
                    table_a, table_b, table_c):
    """Assemble the PDF summary report.

    Parameters
    ----------
    times : list[datetime]
        UTC flux timestamps (used for observation-window metadata).
    fig6_path, fig7_path, fig8_path : str
        Absolute paths to the saved PNG figures.
    table_a, table_b, table_c : pd.DataFrame
        The three numeric tables.

    Returns
    -------
    str
        Absolute path of the saved PDF.
    """
    pdf_path = os.path.join(_OUTPUT_DIR, "goes_summary_report.pdf")

    valid_times = [t for t in times if _is_valid_time(t)]
    time_start = min(valid_times) if valid_times else None
    time_end = max(valid_times) if valid_times else None
    if time_start and time_end:
        obs_window = (
            f"{time_start.strftime('%Y-%m-%d %H:%M')} UTC"
            f"  \u2192  "
            f"{time_end.strftime('%Y-%m-%d %H:%M')} UTC"
        )
    else:
        obs_window = "unknown"

    with PdfPages(pdf_path) as pdf:

        # ------------------------------------------------------------------ #
        # Title page
        # ------------------------------------------------------------------ #
        fig_title = plt.figure(figsize=(8.5, 11))
        ax_t = fig_title.add_subplot(111)
        ax_t.axis("off")
        title_text = (
            "GOES 7-Day Summary for Figures 6\u20138\n"
            "\n"
            "GOES data source: NOAA SWPC API\n"
            f"Observation window: {obs_window}\n"
            f"Rolling variance window length: L = {WINDOW_L}"
        )
        ax_t.text(
            0.5, 0.55, title_text,
            ha="center", va="center", fontsize=14,
            transform=ax_t.transAxes,
            multialignment="center",
        )
        pdf.savefig(fig_title, bbox_inches="tight")
        plt.close(fig_title)

        # ------------------------------------------------------------------ #
        # Page for Figure 6 + Table A
        # ------------------------------------------------------------------ #
        fig_p6 = plt.figure(figsize=(8.5, 11))
        fig_p6.suptitle("Figure 6 \u2014 GOES X-ray Flux  |  Table A", fontsize=10)

        ax_img6 = fig_p6.add_axes([0.05, 0.45, 0.90, 0.50])
        ax_img6.axis("off")
        ax_img6.imshow(imread(fig6_path), aspect="auto")

        ax_tbl_a = fig_p6.add_axes([0.05, 0.02, 0.90, 0.40])
        _render_df_table(ax_tbl_a, table_a)

        pdf.savefig(fig_p6, bbox_inches="tight")
        plt.close(fig_p6)

        # ------------------------------------------------------------------ #
        # Page for Figure 7 + Table B
        # ------------------------------------------------------------------ #
        fig_p7 = plt.figure(figsize=(8.5, 11))
        fig_p7.suptitle("Figure 7 \u2014 Rolling Variance  |  Table B", fontsize=10)

        ax_img7 = fig_p7.add_axes([0.05, 0.45, 0.90, 0.50])
        ax_img7.axis("off")
        ax_img7.imshow(imread(fig7_path), aspect="auto")

        ax_tbl_b = fig_p7.add_axes([0.05, 0.02, 0.90, 0.40])
        _render_df_table(ax_tbl_b, table_b)

        pdf.savefig(fig_p7, bbox_inches="tight")
        plt.close(fig_p7)

        # ------------------------------------------------------------------ #
        # Page for Figure 8 + Table C
        # ------------------------------------------------------------------ #
        fig_p8 = plt.figure(figsize=(8.5, 11))
        fig_p8.suptitle("Figure 8 \u2014 Flare Event Overlay  |  Table C", fontsize=10)

        ax_img8 = fig_p8.add_axes([0.05, 0.45, 0.90, 0.50])
        ax_img8.axis("off")
        ax_img8.imshow(imread(fig8_path), aspect="auto")

        ax_tbl_c = fig_p8.add_axes([0.05, 0.02, 0.90, 0.40])
        _render_df_table(ax_tbl_c, table_c)

        pdf.savefig(fig_p8, bbox_inches="tight")
        plt.close(fig_p8)

    return pdf_path


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    os.makedirs(_OUTPUT_DIR, exist_ok=True)

    print("Loading GOES X-ray flux \u2026")
    times, flux = _load_flux()
    print(f"  {len(times)} data points loaded.")

    print("Loading NOAA flare catalogue \u2026")
    flare_data = _load_flares()
    print(f"  {len(flare_data)} flare event(s) found.")

    print(f"Computing rolling variance (L={WINDOW_L}) \u2026")
    var = rolling_variance(flux, WINDOW_L)

    print("Constructing tables \u2026")
    table_a = build_table_a(times, flux)
    table_b = build_table_b(times, var)
    table_c = build_table_c(times, flux, flare_data)

    print("Exporting CSV files \u2026")
    csv_a = os.path.join(_OUTPUT_DIR, "goes_table_a_flux.csv")
    csv_b = os.path.join(_OUTPUT_DIR, "goes_table_b_rolling_variance.csv")
    csv_c = os.path.join(_OUTPUT_DIR, "goes_table_c_flare_overlay.csv")
    table_a.to_csv(csv_a, index=False)
    table_b.to_csv(csv_b, index=False)
    table_c.to_csv(csv_c, index=False)

    print("Generating figures \u2026")
    p6 = make_fig6(times, flux)
    p7 = make_fig7(times, var)
    p8 = make_fig8(times, flux, flare_data)

    print("Assembling PDF report \u2026")
    pdf_path = make_pdf_report(times, p6, p7, p8, table_a, table_b, table_c)

    print("\nOutput files:")
    for path in (csv_a, csv_b, csv_c, p6, p7, p8, pdf_path):
        print(os.path.abspath(path))
