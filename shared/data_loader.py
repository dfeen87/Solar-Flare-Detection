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
from datetime import date, datetime, timedelta, timezone
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

# Long-range caching root
_RAW_CACHE_ROOT = _REPO_ROOT / "data" / "raw" / "goes"

# Range-source mapping: dataset_key -> same SWPC URL as used in _SOURCES
_RANGE_SOURCES = {
    "xray_flux":        _SOURCES["xray"][1],
    "xray_background":  _SOURCES["background"][1],
    "flare_catalogue":  _SOURCES["flares"][1],
    "euvs":             _SOURCES["euvs"][1],
    "magnetometer":     _SOURCES["magneto"][1],
}

# Range URL templates: dataset_key -> format string with {start} and {end}
# Derived from existing 7-day filenames by stripping "-7-day".
_SWPC_BASE = "https://services.swpc.noaa.gov/json/goes/primary"
_RANGE_URL_TEMPLATES = {
    "xray_flux":       f"{_SWPC_BASE}/xrays.json?start={{start}}&end={{end}}",
    "xray_background": f"{_SWPC_BASE}/xray-background.json?start={{start}}&end={{end}}",
    "flare_catalogue": f"{_SWPC_BASE}/xray-flares.json?start={{start}}&end={{end}}",
    "euvs":            f"{_SWPC_BASE}/euvs.json?start={{start}}&end={{end}}",
    "magnetometer":    f"{_SWPC_BASE}/magnetometers.json?start={{start}}&end={{end}}",
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
    """Parse an ISO-8601-like timestamp string into a datetime object.

    Returns ``None`` when *value* is ``None`` or cannot be parsed.
    """
    if value is None:
        return None
    # NOAA timestamps look like "2025-01-15T12:34:00Z" or "2025-01-15 12:34:00"
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except (ValueError, TypeError):
            continue
    # Last resort: pandas parser (pd.to_datetime may return None for unparseable
    # input in some pandas versions, so guard before calling .to_pydatetime())
    result = pd.to_datetime(value, errors="coerce")
    if result is None or pd.isna(result):
        return None
    return result.to_pydatetime()


def _parse_ts_utc(value: str):
    """Parse an ISO-8601-like timestamp into a UTC-aware datetime.

    Returns ``None`` when *value* is ``None`` or unparsable.
    """
    if value is None:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(value, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, TypeError):
            continue
    return None


def _normalize_date_input(value) -> datetime:
    """Convert *value* to a UTC-aware datetime at midnight.

    Accepts ``datetime``, ``date``, or ISO string (``YYYY-MM-DD`` or full
    ISO timestamp).
    """
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    if isinstance(value, str):
        # Try full ISO timestamp first
        parsed = _parse_ts_utc(value)
        if parsed is not None:
            return parsed
        # Try date-only
        try:
            d = date.fromisoformat(value)
            return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
        except (ValueError, TypeError):
            pass
    raise ValueError(f"Cannot normalize date input: {value!r}")


def _validate_range(start_dt: datetime, end_dt: datetime) -> None:
    """Raise ``ValueError`` unless *start_dt* < *end_dt* and both are UTC."""
    if start_dt.tzinfo is None or end_dt.tzinfo is None:
        raise ValueError("Both start and end must be UTC-aware datetimes")
    if start_dt >= end_dt:
        raise ValueError(
            f"start ({start_dt.isoformat()}) must be before end ({end_dt.isoformat()})"
        )


def _iter_7d_windows(start_dt: datetime, end_dt: datetime):
    """Return contiguous 7-day windows covering [start_dt, end_dt)."""
    windows = []
    cursor = start_dt
    step = timedelta(days=7)
    while cursor < end_dt:
        win_end = min(cursor + step, end_dt)
        windows.append((cursor, win_end))
        cursor = cursor + step
    return windows


def _cache_path(dataset_key: str, start_dt: datetime, end_dt: datetime) -> Path:
    """Return the cache file path for a dataset key and date range."""
    s = start_dt.date().isoformat()
    e = end_dt.date().isoformat()
    return _RAW_CACHE_ROOT / dataset_key / f"{s}_to_{e}.json"


def _read_cached_json(path: Path) -> list:
    """Read cached JSON array from *path*."""
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError(f"Cached JSON at {path} is not a list")
    return data


def _write_cached_json(path: Path, payload: list) -> None:
    """Write *payload* (must be a list) as JSON to *path*."""
    if not isinstance(payload, list):
        raise ValueError("Cached payload must be a list")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)


def _fetch_swpc_json(url: str, timeout_s: int = 30) -> list:
    """Fetch JSON from a SWPC URL and return parsed list."""
    try:
        with urlopen(url, timeout=timeout_s) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(f"SWPC fetch failed for {url}: {exc}") from exc
    if not isinstance(data, list):
        raise RuntimeError(f"Expected JSON array from {url}, got {type(data).__name__}")
    return data


def _load_swpc_range_raw(dataset_key: str, start, end, *,
                         force_refresh: bool = False) -> list:
    """Load raw JSON records for *dataset_key* over [start, end).

    Uses range URL templates and caches the result under
    ``data/raw/goes/<dataset_key>/<start>_to_<end>.json``.
    """
    start_dt = _normalize_date_input(start)
    end_dt = _normalize_date_input(end)
    _validate_range(start_dt, end_dt)

    cp = _cache_path(dataset_key, start_dt, end_dt)

    if cp.exists() and not force_refresh:
        return _read_cached_json(cp)

    if dataset_key not in _RANGE_URL_TEMPLATES:
        raise RuntimeError(
            f"Long-range URL template not configured for {dataset_key}"
        )

    template = _RANGE_URL_TEMPLATES[dataset_key]
    combined = []
    for win_start, win_end in _iter_7d_windows(start_dt, end_dt):
        url = template.format(
            start=win_start.date().isoformat(),
            end=win_end.date().isoformat(),
        )
        try:
            records = _fetch_swpc_json(url)
        except RuntimeError as exc:
            raise RuntimeError(
                f"Failed fetching {dataset_key} window "
                f"[{win_start.date()}, {win_end.date()}): {exc}"
            ) from exc
        combined.extend(records)

    _write_cached_json(cp, combined)
    return combined


# ---------------------------------------------------------------------------
# Range-loader DataFrame converters
# ---------------------------------------------------------------------------

def _records_to_xray_flux_df(records: list, start_dt, end_dt) -> pd.DataFrame:
    """Convert raw xray records to a flux DataFrame filtered to [start_dt, end_dt)."""
    rows = []
    for r in records:
        if r.get("energy", "") == "0.1-0.8nm":
            t = _parse_ts_utc(r.get("time_tag"))
            if t is None:
                continue
            rows.append({"time": t, "flux": float(r.get("flux", float("nan")))})
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["time", "flux"])
    df.sort_values("time", inplace=True)
    df.drop_duplicates(subset="time", keep="last", inplace=True)
    df = df[(df["time"] >= start_dt) & (df["time"] < end_dt)]
    df.reset_index(drop=True, inplace=True)
    return df


def _records_to_xray_background_df(records: list, start_dt, end_dt) -> pd.DataFrame:
    """Convert raw xray-background records to DataFrame filtered to [start_dt, end_dt)."""
    rows = []
    for r in records:
        t = _parse_ts_utc(r.get("time_tag"))
        if t is None:
            continue
        rows.append({
            "time": t,
            "background_flux": float(r.get("flux", float("nan"))),
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["time", "background_flux"])
    df.sort_values("time", inplace=True)
    df.drop_duplicates(subset="time", keep="last", inplace=True)
    df = df[(df["time"] >= start_dt) & (df["time"] < end_dt)]
    df.reset_index(drop=True, inplace=True)
    return df


def _records_to_euvs_df(records: list, start_dt, end_dt) -> pd.DataFrame:
    """Convert raw EUVS records to DataFrame filtered to [start_dt, end_dt)."""
    if not records:
        return pd.DataFrame(columns=["time"])
    _meta_keys = {"time_tag", "satellite"}
    sample_records = records[:50]
    all_keys = set()
    for r in sample_records:
        all_keys.update(r.keys())
    channel_keys = sorted(k for k in all_keys if k not in _meta_keys)

    rows = []
    for r in records:
        t = _parse_ts_utc(r.get("time_tag"))
        if t is None:
            continue
        row = {"time": t}
        for ch in channel_keys:
            val = r.get(ch)
            try:
                row[ch] = float(val) if val is not None else float("nan")
            except (ValueError, TypeError):
                row[ch] = float("nan")
        rows.append(row)
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["time"] + channel_keys)
    df.sort_values("time", inplace=True)
    df.drop_duplicates(subset="time", keep="last", inplace=True)
    df = df[(df["time"] >= start_dt) & (df["time"] < end_dt)]
    df.reset_index(drop=True, inplace=True)
    return df


def _records_to_magnetometer_df(records: list, start_dt, end_dt) -> pd.DataFrame:
    """Convert raw magnetometer records to DataFrame filtered to [start_dt, end_dt)."""
    rows = []
    for r in records:
        t = _parse_ts_utc(r.get("time_tag"))
        if t is None:
            continue
        rows.append({"time": t, "He": float(r.get("He", float("nan")))})
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["time", "He"])
    df.sort_values("time", inplace=True)
    df.drop_duplicates(subset="time", keep="last", inplace=True)
    df = df[(df["time"] >= start_dt) & (df["time"] < end_dt)]
    df.reset_index(drop=True, inplace=True)
    return df


def _records_to_flare_catalogue_df(records: list, start_dt, end_dt) -> pd.DataFrame:
    """Convert raw flare-catalogue records to DataFrame filtered to [start_dt, end_dt)."""
    rows = []
    for r in records:
        tb = _parse_ts_utc(r.get("begin_time"))
        if tb is None:
            continue
        class_str = r.get("class", "")
        class_type = class_str[0] if class_str else ""
        try:
            class_num = float(class_str[1:]) if len(class_str) > 1 else float("nan")
        except ValueError:
            class_num = float("nan")
        rows.append({
            "time_begin": tb,
            "time_max":   _parse_ts_utc(r.get("max_time")),
            "time_end":   _parse_ts_utc(r.get("end_time")),
            "class_type": class_type,
            "class_num":  class_num,
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=[
            "time_begin", "time_max", "time_end", "class_type", "class_num"
        ])
    df.sort_values("time_begin", inplace=True)
    df = df[(df["time_begin"] >= start_dt) & (df["time_begin"] < end_dt)]
    df.reset_index(drop=True, inplace=True)
    return df


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


# ---------------------------------------------------------------------------
# Public API — Long-range loaders
# ---------------------------------------------------------------------------

def load_goes_xray_range(start, end, *, include_background: bool = False,
                         force_refresh: bool = False) -> pd.DataFrame:
    r"""Load GOES 0.1–0.8 nm X-ray flux over an arbitrary date range.

    X(t) denotes the GOES 0.1–0.8 nm soft X‑ray flux time series (W m⁻²).

    Derived quantities (computed elsewhere):
        Var_L[X(t)] — rolling variance over a window of length L samples.

    Parameters
    ----------
    start, end : date-like
        Half-open interval [start, end). Accepts ``datetime``, ``date``,
        or ISO ``YYYY-MM-DD`` strings.
    include_background : bool
        If True, also fetch the X-ray background and merge on ``time``
        (outer join), adding a ``background_flux`` column.
    force_refresh : bool
        If True, bypass cache and re-fetch from SWPC.

    Returns
    -------
    pd.DataFrame
        Columns: ``time`` (UTC-aware datetime), ``flux`` (float).
        If *include_background* is True: also ``background_flux`` (float).

    Notes
    -----
    Returned timestamps are UTC-aware datetime objects.
    Range semantics: [start, end) half-open interval.
    Cached under ``data/raw/goes/xray_flux/<start>_to_<end>.json``.
    """
    start_dt = _normalize_date_input(start)
    end_dt = _normalize_date_input(end)
    records = _load_swpc_range_raw("xray_flux", start_dt, end_dt,
                                   force_refresh=force_refresh)
    df = _records_to_xray_flux_df(records, start_dt, end_dt)

    if include_background:
        bg_records = _load_swpc_range_raw("xray_background", start_dt, end_dt,
                                          force_refresh=force_refresh)
        bg_df = _records_to_xray_background_df(bg_records, start_dt, end_dt)
        df = pd.merge(df, bg_df, on="time", how="outer")
        df.sort_values("time", inplace=True)
        df.reset_index(drop=True, inplace=True)

    return df


def load_goes_euv_range(start, end, *,
                        force_refresh: bool = False) -> pd.DataFrame:
    r"""Load GOES EUVS irradiance over an arbitrary date range.

    EUV(t) denotes the GOES EUVS irradiance time series (channel-dependent
    units as provided by SWPC).

    Derived quantities (computed elsewhere):
        |d/dt EUV(t)| — magnitude of the time derivative, typically
        approximated by finite differences after time alignment.

    Parameters
    ----------
    start, end : date-like
        Half-open interval [start, end).
    force_refresh : bool
        If True, bypass cache and re-fetch from SWPC.

    Returns
    -------
    pd.DataFrame
        Columns: ``time`` (UTC-aware datetime) plus one column per
        irradiance channel present in the SWPC product.

    Notes
    -----
    Returned timestamps are UTC-aware datetime objects.
    Range semantics: [start, end) half-open interval.
    Cached under ``data/raw/goes/euvs/<start>_to_<end>.json``.
    """
    start_dt = _normalize_date_input(start)
    end_dt = _normalize_date_input(end)
    records = _load_swpc_range_raw("euvs", start_dt, end_dt,
                                   force_refresh=force_refresh)
    return _records_to_euvs_df(records, start_dt, end_dt)


def load_goes_magnetometer_range(start, end, *,
                                 force_refresh: bool = False) -> pd.DataFrame:
    r"""Load GOES magnetometer data over an arbitrary date range.

    B(t) denotes a magnetic-field variability proxy, here taken as the GOES
    magnetometer parallel component He(t) (nT).

    Derived quantities (computed elsewhere):
        Var_L[B(t)] — rolling variance over a window of length L samples.

    Parameters
    ----------
    start, end : date-like
        Half-open interval [start, end).
    force_refresh : bool
        If True, bypass cache and re-fetch from SWPC.

    Returns
    -------
    pd.DataFrame
        Columns: ``time`` (UTC-aware datetime), ``He`` (float, nT).

    Notes
    -----
    Returned timestamps are UTC-aware datetime objects.
    Range semantics: [start, end) half-open interval.
    Cached under ``data/raw/goes/magnetometer/<start>_to_<end>.json``.
    """
    start_dt = _normalize_date_input(start)
    end_dt = _normalize_date_input(end)
    records = _load_swpc_range_raw("magnetometer", start_dt, end_dt,
                                   force_refresh=force_refresh)
    return _records_to_magnetometer_df(records, start_dt, end_dt)


def load_flare_catalogue_range(start, end, *,
                               force_refresh: bool = False) -> pd.DataFrame:
    r"""Load GOES flare event catalogue over an arbitrary date range.

    {t_k} denotes flare onset times, identified with catalogue time_begin.

    Parameters
    ----------
    start, end : date-like
        Half-open interval [start, end).
    force_refresh : bool
        If True, bypass cache and re-fetch from SWPC.

    Returns
    -------
    pd.DataFrame
        Columns: ``time_begin``, ``time_max``, ``time_end`` (UTC-aware
        datetime), ``class_type`` (str), ``class_num`` (float).

    Notes
    -----
    Returned timestamps are UTC-aware datetime objects.
    Range semantics: [start, end) half-open interval.
    Cached under ``data/raw/goes/flare_catalogue/<start>_to_<end>.json``.
    """
    start_dt = _normalize_date_input(start)
    end_dt = _normalize_date_input(end)
    records = _load_swpc_range_raw("flare_catalogue", start_dt, end_dt,
                                   force_refresh=force_refresh)
    return _records_to_flare_catalogue_df(records, start_dt, end_dt)
