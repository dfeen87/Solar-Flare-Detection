"""
shared/prepare_real_data.py
===========================
Prepare real GOES-18 XRS 1-minute data for use with the existing pipeline.

Reads ``noaa_goes18_xrs_1m.csv.zip`` from the repository root, converts
J2000 epoch seconds to UTC timestamps, cleans the data, and writes
SWPC-format JSON cache files that ``shared/data_loader.py`` will read
transparently — no modifications to the loaders or experiment scripts needed.

Four aligned intervals are derived from the earliest 2024 timestamp (t0):

    ============  ===========  ===========
    Interval      Start        End (excl.)
    ============  ===========  ===========
    1-month       2024-01-01   2024-01-31
    3-month       2024-01-01   2024-04-01
    6-month       2024-01-01   2024-07-01
    1-year        2024-01-01   2024-12-31
    ============  ===========  ===========

Cache files are written to ``data/raw/goes/<dataset_key>/<start>_to_<end>.json``
and are excluded from Git (see ``.gitignore``).  Run this script once before
executing any of the ``eval_*_real.py`` experiment scripts.

Usage
-----
::

    python shared/prepare_real_data.py
    python shared/prepare_real_data.py --zip-path path/to/noaa_goes18_xrs_1m.csv.zip

GOES-18 XRS CSV columns
-----------------------
time (seconds since 2000-01-01 12:00:00)  — J2000 epoch seconds
shortwave (W/m^2)                          — 0.5–4 Å (0.05–0.4 nm) channel
longwave (W/m^2)                           — 1–8 Å (0.1–0.8 nm) channel
shortwave_flag, longwave_flag              — quality flags (0 = good)
shortwave_masked (W/m^2)                   — quality-filtered shortwave
longwave_masked (W/m^2)                    — quality-filtered longwave

Mapping to pipeline datasets
-----------------------------
xray_flux        ← longwave_masked  (0.1–0.8 nm, energy key "0.1-0.8nm")
xray_background  ← 12-hour rolling median of longwave_masked
magnetometer He  ← normalised longwave_masked scaled to [90, 110] nT range
euvs e_low       ← shortwave_masked  (0.05–0.4 nm, used as EUV proxy)
flare_catalogue  ← empty (no flare catalogue in the XRS CSV)

References
----------
PAPER.md §4.1, Table 1 — observational channels.
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_ZIP = _REPO_ROOT / "noaa_goes18_xrs_1m.csv.zip"
_CACHE_ROOT = _REPO_ROOT / "data" / "raw" / "goes"

# J2000 epoch: 2000-01-01T12:00:00 UTC
_J2000 = datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

# ---------------------------------------------------------------------------
# Interval definitions (start always = t0 = first 2024 timestamp)
# ---------------------------------------------------------------------------

_T0 = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

_INTERVALS: dict[str, tuple[datetime, datetime]] = {
    "1m":  (_T0, _T0 + timedelta(days=30)),
    "3m":  (_T0, _T0 + timedelta(days=90)),
    "6m":  (_T0, _T0 + timedelta(days=182)),
    "1y":  (_T0, _T0 + timedelta(days=365)),
}

# Human-readable labels for progress messages
_INTERVAL_LABELS = {"1m": "1-month", "3m": "3-month", "6m": "6-month", "1y": "1-year"}


# ---------------------------------------------------------------------------
# Data loading and cleaning
# ---------------------------------------------------------------------------

def load_and_clean(zip_path: Path) -> pd.DataFrame:
    """Load, clean, and return the GOES-18 XRS DataFrame.

    Steps
    -----
    1. Read ``noaa_goes18_xrs_1m.csv`` from the ZIP archive (skipping macOS
       metadata entries).
    2. Convert J2000 epoch seconds to UTC-aware ``timestamp`` column.
    3. Drop rows where ``longwave_masked`` or ``shortwave_masked`` are NaN.
    4. Interpolate any residual gaps to enforce uniform 1-minute cadence.
    5. Convert all flux columns to float64.

    Returns
    -------
    pd.DataFrame
        Cleaned DataFrame with columns:
        ``timestamp``, ``xrs_short``, ``xrs_long``
        sorted by ``timestamp`` (UTC-aware).
    """
    print(f"[prepare_real_data] Reading {zip_path} …")
    with zipfile.ZipFile(zip_path) as zf:
        csv_names = [n for n in zf.namelist()
                     if not n.startswith("__MACOSX") and n.endswith(".csv")]
        if not csv_names:
            raise FileNotFoundError(f"No CSV file found inside {zip_path}")
        with zf.open(csv_names[0]) as fh:
            raw = pd.read_csv(fh)

    # Rename columns for clarity
    raw.columns = [c.strip() for c in raw.columns]
    col_time = "time (seconds since 2000-01-01 12:00:00)"
    col_sw   = "shortwave_masked (W/m^2)"
    col_lw   = "longwave_masked (W/m^2)"

    # Build UTC timestamps using vectorised arithmetic
    epoch_ns = int(_J2000.timestamp() * 1e9)
    timestamps = pd.to_datetime(
        epoch_ns + (raw[col_time].astype(float) * 1e9).astype("int64"),
        utc=True,
    )

    df = pd.DataFrame({
        "timestamp": timestamps,
        "xrs_short": raw[col_sw].astype(float),
        "xrs_long":  raw[col_lw].astype(float),
    })

    # Drop rows with NaN flux
    df.dropna(subset=["xrs_short", "xrs_long"], inplace=True)

    # Sort and deduplicate
    df.sort_values("timestamp", inplace=True)
    df.drop_duplicates(subset="timestamp", keep="last", inplace=True)
    df.reset_index(drop=True, inplace=True)

    # Enforce uniform 1-minute cadence via reindex + linear interpolation
    if not df.empty:
        t_min = df["timestamp"].iloc[0]
        t_max = df["timestamp"].iloc[-1]
        full_index = pd.date_range(t_min, t_max, freq="1min", tz="UTC")
        df = df.set_index("timestamp").reindex(full_index)
        df.index.name = "timestamp"
        # Interpolate gaps (limit to 60 minutes to avoid filling large gaps)
        df["xrs_short"] = df["xrs_short"].interpolate(method="time", limit=60)
        df["xrs_long"]  = df["xrs_long"].interpolate(method="time", limit=60)
        df.dropna(inplace=True)
        df = df.reset_index()

    print(f"[prepare_real_data] Loaded {len(df):,} rows "
          f"({df['timestamp'].iloc[0]} — {df['timestamp'].iloc[-1]})")
    return df


# ---------------------------------------------------------------------------
# JSON record builders (SWPC wire format)
# ---------------------------------------------------------------------------

def _ts_str(ts: pd.Timestamp) -> str:
    """Format a pandas Timestamp as an ISO-8601 UTC string."""
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


def _build_xray_flux_records(df: pd.DataFrame) -> list[dict]:
    """Build SWPC xray-flux JSON records from longwave_masked.

    The ``data_loader._records_to_xray_flux_df`` function filters on
    ``energy == "0.1-0.8nm"`` (long-wave channel), so all records carry
    that energy key.
    """
    return [
        {
            "time_tag": _ts_str(row.timestamp),
            "flux":     float(row.xrs_long),
            "energy":   "0.1-0.8nm",
        }
        for row in df.itertuples(index=False)
    ]


def _build_xray_background_records(df: pd.DataFrame) -> list[dict]:
    """Build SWPC xray-background JSON records.

    Background is approximated by a 12-hour (720-sample) rolling median of
    the long-wave flux, representing the quiet-Sun baseline level.
    """
    bg = df["xrs_long"].rolling(window=720, center=True, min_periods=1).median()
    return [
        {"time_tag": _ts_str(row.timestamp), "flux": float(bg_val)}
        for row, bg_val in zip(df.itertuples(index=False), bg)
    ]


def _build_magnetometer_records(df: pd.DataFrame) -> list[dict]:
    """Build SWPC magnetometer JSON records.

    Because the XRS CSV contains no magnetometer data, a synthetic He(t)
    proxy is constructed from the normalised long-wave flux:

        He(t) = 100 + (xrs_long − μ) / σ × 10

    This centres He around 100 nT (typical quiet-Sun value) with ±10 nT
    variation proportional to the flux variability.  The backward-difference
    operator ΔΦ(t) used downstream is therefore non-trivial and physically
    motivated by the X-ray signal.
    """
    lw = df["xrs_long"].to_numpy(dtype=float)
    mu = np.nanmean(lw)
    sigma = np.nanstd(lw)
    if sigma == 0:
        sigma = 1.0
    he = 100.0 + (lw - mu) / sigma * 10.0
    return [
        {"time_tag": _ts_str(row.timestamp), "He": float(he_val)}
        for row, he_val in zip(df.itertuples(index=False), he)
    ]


def _build_euvs_records(df: pd.DataFrame) -> list[dict]:
    """Build SWPC EUVS JSON records.

    The short-wave XRS channel (0.05–0.4 nm, shortwave_masked) is used as a
    proxy for the low-energy EUV channel ``e_low``.  Both originate from
    coronal emission and scale similarly with solar activity.
    """
    return [
        {
            "time_tag": _ts_str(row.timestamp),
            "e_low":    float(row.xrs_short),
        }
        for row in df.itertuples(index=False)
    ]


def _build_flare_catalogue_records(_df: pd.DataFrame) -> list[dict]:
    """Return an empty flare catalogue.

    The XRS CSV contains only flux measurements; no flare detection has been
    applied.  An empty catalogue means ``evaluate_precursor`` will compute
    AUC metrics without positive events (valid for signal distribution
    analysis).
    """
    return []


# ---------------------------------------------------------------------------
# Cache-file writer
# ---------------------------------------------------------------------------

_BUILDERS = {
    "xray_flux":       _build_xray_flux_records,
    "xray_background": _build_xray_background_records,
    "magnetometer":    _build_magnetometer_records,
    "euvs":            _build_euvs_records,
    "flare_catalogue": _build_flare_catalogue_records,
}


def _cache_path(dataset_key: str, start_dt: datetime, end_dt: datetime) -> Path:
    """Mirror the cache-path logic of ``shared/data_loader.py``."""
    s = start_dt.date().isoformat()
    e = end_dt.date().isoformat()
    return _CACHE_ROOT / dataset_key / f"{s}_to_{e}.json"


def write_interval_caches(df: pd.DataFrame, name: str,
                          start: datetime, end: datetime) -> None:
    """Slice *df* to [start, end) and write all five dataset cache files."""
    label = _INTERVAL_LABELS.get(name, name)
    mask = (df["timestamp"] >= start) & (df["timestamp"] < end)
    subset = df.loc[mask].copy().reset_index(drop=True)
    print(f"[prepare_real_data] {label}: {len(subset):,} rows "
          f"({start.date()} — {end.date()}, excl.)")

    for dataset_key, builder in _BUILDERS.items():
        records = builder(subset)
        path = _cache_path(dataset_key, start, end)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(records, fh, separators=(",", ":"))
        print(f"  ✓ {path.relative_to(_REPO_ROOT)}  ({len(records):,} records)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: "list[str] | None" = None) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare real GOES-18 XRS data for the Solar Flare Detection pipeline."
        ),
    )
    parser.add_argument(
        "--zip-path",
        default=str(_DEFAULT_ZIP),
        metavar="PATH",
        help=f"Path to noaa_goes18_xrs_1m.csv.zip (default: {_DEFAULT_ZIP})",
    )
    args = parser.parse_args(argv)

    zip_path = Path(args.zip_path)
    if not zip_path.exists():
        print(f"ERROR: ZIP file not found: {zip_path}", file=sys.stderr)
        sys.exit(1)

    df = load_and_clean(zip_path)

    for interval_name, (start, end) in _INTERVALS.items():
        write_interval_caches(df, interval_name, start, end)

    print("\n[prepare_real_data] All cache files written successfully.")
    print("You can now run the real-data experiment scripts:")
    for name in ("one_month", "three_month", "six_month", "one_year"):
        print(f"  python experiments/eval_{name}_real.py")


if __name__ == "__main__":
    main()
