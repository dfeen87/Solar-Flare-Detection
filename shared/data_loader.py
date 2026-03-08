"""
shared/data_loader.py
=====================
Loads observational solar-physics data from local JSON cache files or, when
those files are absent, fetches them directly from the NOAA Space Weather
Prediction Center (SWPC) public REST API.

Data sources (§4.1, Table 1 of PAPER.md):
  - GOES X-ray flux          xrays-7-day.json
  - GOES flare catalogue     xray-flares-7-day.json
  - GOES X-ray background    xray-background-7-day.json
  - GOES magnetometer        magnetometers-7-day.json
  - GOES EUVS irradiance     euvs-7-day.json

All functions return a pandas DataFrame with a parsed `time` column (or
equivalent timestamp columns for flare events).

References
----------
PAPER.md §4.1, Table 1 — observational channels and physical interpretations.
Krüger & Feeney (2026) — see CITATIONS.md.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError

import pandas as pd

# ---------------------------------------------------------------------------
# Paths and URLs
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DATA_ROOT = _REPO_ROOT / "assets" / "data"

_SOURCES = {
    "xray":       ("xray/xrays-7-day.json",
                   "https://services.swpc.noaa.gov/json/goes/primary/xrays-7-day.json"),
    "flares":     ("xray/xray-flares-7-day.json",
                   "https://services.swpc.noaa.gov/json/goes/primary/xray-flares-7-day.json"),
    "background": ("xray/xray-background-7-day.json",
                   "https://services.swpc.noaa.gov/json/goes/primary/xray-background-7-day.json"),
    "magneto":    ("magnetometers/magnetometers-7-day.json",
                   "https://services.swpc.noaa.gov/json/goes/primary/magnetometers-7-day.json"),
    "euvs":       ("euvs/euvs-7-day.json",
                   "https://services.swpc.noaa.gov/json/goes/primary/euvs-7-day.json"),
}

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_json(key: str) -> list:
    """Return raw JSON list for *key*, using local cache or NOAA fallback."""
    local_path, url = _SOURCES[key]
    full_path = _DATA_ROOT / local_path

    if full_path.exists():
        with open(full_path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    # Fallback: fetch from NOAA SWPC
    try:
        with urlopen(url, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except URLError as exc:
        raise RuntimeError(
            f"Local file '{full_path}' not found and NOAA fetch failed: {exc}"
        ) from exc


def _parse_ts(value: str) -> datetime:
    """Parse an ISO-8601-like timestamp string into a datetime object."""
    # NOAA timestamps look like "2025-01-15T12:34:00Z" or "2025-01-15 12:34:00"
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except (ValueError, TypeError):
            continue
    # Last resort: pandas parser
    return pd.to_datetime(value).to_pydatetime()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_xray_flux() -> pd.DataFrame:
    """Load GOES X-ray flux (0.1–0.8 nm channel).

    Returns
    -------
    DataFrame with columns:
        time  : datetime — timestamp of measurement
        flux  : float   — X-ray flux in W m⁻² (0.1–0.8 nm channel)

    References: PAPER.md §4.1, Table 1 — X(t) channel.
    """
    records = _load_json("xray")
    rows = []
    for r in records:
        # NOAA JSON contains both channels; select 0.1–0.8 nm ("long")
        if r.get("energy", "") == "0.1-0.8nm":
            rows.append({
                "time": _parse_ts(r["time_tag"]),
                "flux": float(r.get("flux", float("nan"))),
            })
    df = pd.DataFrame(rows)
    df.sort_values("time", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def load_xray_flares() -> pd.DataFrame:
    """Load GOES flare event catalogue.

    Returns
    -------
    DataFrame with columns:
        time_begin  : datetime — flare start time
        time_max    : datetime — peak time
        time_end    : datetime — end time
        class_type  : str     — GOES flare class letter (A, B, C, M, X)
        class_num   : float   — numeric class qualifier (e.g. 2.3 for M2.3)

    References: PAPER.md §4.1, Table 1 — flare event catalogue {tₖ}.
    """
    records = _load_json("flares")
    rows = []
    for r in records:
        class_str = r.get("class", "")
        class_type = class_str[0] if class_str else ""
        try:
            class_num = float(class_str[1:]) if len(class_str) > 1 else float("nan")
        except ValueError:
            class_num = float("nan")
        rows.append({
            "time_begin": _parse_ts(r.get("begin_time", "")),
            "time_max":   _parse_ts(r.get("max_time", "")),
            "time_end":   _parse_ts(r.get("end_time", "")),
            "class_type": class_type,
            "class_num":  class_num,
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df.sort_values("time_begin", inplace=True)
        df.reset_index(drop=True, inplace=True)
    return df


def load_xray_background() -> pd.DataFrame:
    """Load GOES X-ray background (quiet-Sun baseline).

    Returns
    -------
    DataFrame with columns:
        time             : datetime — timestamp
        background_flux  : float   — background flux in W m⁻²

    References: PAPER.md §4.1, Table 1 — X_bg(t).
    """
    records = _load_json("background")
    rows = []
    for r in records:
        rows.append({
            "time":            _parse_ts(r["time_tag"]),
            "background_flux": float(r.get("flux", float("nan"))),
        })
    df = pd.DataFrame(rows)
    df.sort_values("time", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def load_magnetometer() -> pd.DataFrame:
    """Load GOES magnetometer data.

    The He (parallel) component is the most relevant proxy for B(t) in the
    PAPER.md context (structural variability S(t)).

    Returns
    -------
    DataFrame with columns:
        time : datetime — timestamp
        He   : float   — parallel magnetic field component (nT)

    References: PAPER.md §4.1, Table 1 — B(t) channel; §6.2 S(t) proxy.
    """
    records = _load_json("magneto")
    rows = []
    for r in records:
        rows.append({
            "time": _parse_ts(r["time_tag"]),
            "He":   float(r.get("He", float("nan"))),
        })
    df = pd.DataFrame(rows)
    df.sort_values("time", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def load_euvs() -> pd.DataFrame:
    """Load GOES EUVS (Extreme UltraViolet Sensor) irradiance data.

    All irradiance channels present in the JSON are retained as separate
    DataFrame columns. Typical NOAA EUVS JSON keys include 'e_low', 'e_mid',
    'e_high', 'e_1', 'e_2', etc. — the exact set depends on the instrument
    version; this function includes whatever is present.

    Returns
    -------
    DataFrame with columns:
        time        : datetime — timestamp
        <channel>   : float   — irradiance for each channel present

    References: PAPER.md §4.1, Table 1 — EUV(t) channel; §6.2 C(t) proxy.
    """
    records = _load_json("euvs")
    if not records:
        return pd.DataFrame()

    # Discover all numeric channel keys (exclude metadata keys)
    _meta_keys = {"time_tag", "satellite", "flux"}
    sample = records[0]
    channel_keys = [k for k in sample if k not in _meta_keys
                    and isinstance(sample[k], (int, float, type(None)))]
    # If no channel keys found, try keys that look like irradiance channels
    if not channel_keys:
        channel_keys = [k for k in sample if k not in _meta_keys and k != "time_tag"]

    rows = []
    for r in records:
        row = {"time": _parse_ts(r["time_tag"])}
        for ch in channel_keys:
            val = r.get(ch)
            row[ch] = float(val) if val is not None else float("nan")
        rows.append(row)

    df = pd.DataFrame(rows)
    df.sort_values("time", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df
