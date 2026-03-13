"""
shared.composite_features — Composite precursor feature assembly.

Assembles ΔΦ(t), X-ray background, and EUV variability into a single
aligned feature table on a unified UTC time grid.

Mathematical definitions
------------------------
Let:
    ΔΦ(tᵢ)  = backward-difference precursor
    X(tᵢ)   = X-ray background
    E(tᵢ)   = EUV variability

The composite feature table is defined as:

    time:       union of all input timestamps (sorted ascending, UTC)
    delta_phi:  ΔΦ(tᵢ) or NaN if tᵢ absent from delta_phi_df
    xray:       X(tᵢ) or NaN if tᵢ absent from xray_df
    euv:        E(tᵢ) or NaN if tᵢ absent from euv_df

No interpolation, forward-filling, or resampling is performed.
"""

import pandas as pd


def _align_on_time(dfs: list, time_col: str) -> pd.DataFrame:
    """Outer-join a list of single-column DataFrames on their time index.

    Parameters
    ----------
    dfs:
        List of DataFrames each with a UTC DatetimeTZDtype index and exactly
        one value column.
    time_col:
        Name to use for the resulting time column.

    Returns
    -------
    pandas.DataFrame
        Outer-joined DataFrame with a ``time`` column and one value column
        per input, sorted by ``time`` ascending.
    """
    if not dfs:
        return pd.DataFrame(columns=[time_col])

    result = dfs[0]
    for df in dfs[1:]:
        result = result.join(df, how="outer")

    result = result.sort_index()
    result.index.name = time_col
    return result.reset_index()


def assemble_precursor_features(
    *,
    delta_phi_df: pd.DataFrame,
    xray_df: pd.DataFrame,
    euv_df: pd.DataFrame,
    time_col: str = "time",
    delta_phi_col: str = "delta_phi",
    xray_col: str = "xray",
    euv_col: str = "euv",
) -> pd.DataFrame:
    """Assemble ΔΦ, X-ray, and EUV into a unified precursor feature table.

    Each input DataFrame is aligned on a common UTC time grid via an outer
    join.  Missing samples are represented as NaN; no interpolation or
    resampling is applied.

    Parameters
    ----------
    delta_phi_df:
        DataFrame containing a UTC-convertible timestamp column and a ΔΦ(t)
        value column.
    xray_df:
        DataFrame containing a UTC-convertible timestamp column and an X-ray
        background value column.
    euv_df:
        DataFrame containing a UTC-convertible timestamp column and an EUV
        variability value column.
    time_col:
        Name of the timestamp column in all three input DataFrames.
    delta_phi_col:
        Name of the ΔΦ value column in *delta_phi_df*.
    xray_col:
        Name of the X-ray value column in *xray_df*.
    euv_col:
        Name of the EUV value column in *euv_df*.

    Returns
    -------
    pandas.DataFrame
        New DataFrame with columns ``["time", "delta_phi", "xray", "euv"]``,
        sorted by ``time`` ascending (UTC).  NaNs are preserved where a
        timestamp is absent from an input.

    Raises
    ------
    ValueError
        If any required column is missing from the corresponding input
        DataFrame.
    """
    # Validate columns
    inputs = [
        ("delta_phi", delta_phi_df, time_col, delta_phi_col),
        ("xray", xray_df, time_col, xray_col),
        ("euv", euv_df, time_col, euv_col),
    ]
    for name, df, tcol, vcol in inputs:
        if tcol not in df.columns:
            raise ValueError(f"{name}_df must contain column: '{tcol}'")
        if vcol not in df.columns:
            raise ValueError(f"{name}_df must contain column: '{vcol}'")

    # Handle all-empty case
    if delta_phi_df.empty and xray_df.empty and euv_df.empty:
        return pd.DataFrame(columns=["time", "delta_phi", "xray", "euv"])

    def _prepare(df: pd.DataFrame, tcol: str, vcol: str, out_col: str) -> pd.DataFrame:
        """Return a copy with a UTC DatetimeTZDtype index and one value column."""
        work = df[[tcol, vcol]].copy()
        work[tcol] = pd.to_datetime(work[tcol], utc=True)
        work = work.sort_values(tcol).set_index(tcol)
        work.index = work.index.rename(tcol)
        work = work.rename(columns={vcol: out_col})
        return work

    prepared = [
        _prepare(delta_phi_df, time_col, delta_phi_col, "delta_phi"),
        _prepare(xray_df, time_col, xray_col, "xray"),
        _prepare(euv_df, time_col, euv_col, "euv"),
    ]

    aligned = _align_on_time(prepared, time_col)

    # Rename the time column to the canonical output name "time" if needed
    if time_col != "time":
        aligned = aligned.rename(columns={time_col: "time"})

    # Ensure the expected column order and that no extra columns are present
    return aligned[["time", "delta_phi", "xray", "euv"]].copy()
