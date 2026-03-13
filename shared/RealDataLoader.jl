"""
RealDataLoader.jl — Julia loader for real GOES-18 XRS 1-minute data.

Reads the cleaned real-data JSON cache files produced by
``shared/prepare_real_data.py`` and returns data in the same NamedTuple
format as ``shared/DataLoader.jl``.  No modifications to ``DataLoader.jl``
are required.

Cache files (written by ``prepare_real_data.py``)
--------------------------------------------------
data/raw/goes/xray_flux/<start>_to_<end>.json
data/raw/goes/xray_background/<start>_to_<end>.json
data/raw/goes/magnetometer/<start>_to_<end>.json
data/raw/goes/euvs/<start>_to_<end>.json
data/raw/goes/flare_catalogue/<start>_to_<end>.json

Usage
-----
```julia
include("shared/RealDataLoader.jl")
using .RealDataLoader

# Load the 1-month real-data interval
flux_data  = load_xray_flux_real("2024-01-01", "2024-01-31")
magn_data  = load_magnetometer_real("2024-01-01", "2024-01-31")
euv_data   = load_euvs_real("2024-01-01", "2024-01-31")
flare_data = load_flare_catalogue_real("2024-01-01", "2024-01-31")
```

Interval strings (start → end, exclusive)
------------------------------------------
1-month  : "2024-01-01" → "2024-01-31"
3-month  : "2024-01-01" → "2024-04-01"
6-month  : "2024-01-01" → "2024-07-01"
1-year   : "2024-01-01" → "2024-12-31"

References
----------
PAPER.md §4.1, Table 1 — observational channels and physical interpretations.
"""
module RealDataLoader

using Dates
using JSON3

export load_xray_flux_real,
       load_xray_background_real,
       load_magnetometer_real,
       load_euvs_real,
       load_flare_catalogue_real

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

const _REPO_ROOT  = joinpath(@__DIR__, "..")
const _CACHE_ROOT = joinpath(_REPO_ROOT, "data", "raw", "goes")

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

"""
    _cache_path(dataset_key, start_str, end_str) -> String

Return the path to the JSON cache file for *dataset_key* and the given
ISO date strings, mirroring ``shared/data_loader.py``'s ``_cache_path``.
"""
function _cache_path(dataset_key::String, start_str::String, end_str::String)
    return joinpath(_CACHE_ROOT, dataset_key, "$(start_str)_to_$(end_str).json")
end


"""
    _load_cache(dataset_key, start_str, end_str) -> JSON3 array

Load the pre-built JSON cache file.  Raises an informative error when the
file is absent (i.e. ``prepare_real_data.py`` has not been run yet).
"""
function _load_cache(dataset_key::String, start_str::String, end_str::String)
    path = _cache_path(dataset_key, start_str, end_str)
    if !isfile(path)
        error(
            "Cache file not found: $path\n" *
            "Run 'python shared/prepare_real_data.py' first to generate the " *
            "real-data cache files."
        )
    end
    return JSON3.read(read(path, String))
end


"""
    _parse_ts(value) -> DateTime

Parse an ISO-8601 UTC timestamp string (e.g. \"2024-01-01T00:01:00Z\").
"""
function _parse_ts(value::Union{String, AbstractString})
    s = endswith(value, "Z") ? value[1:end-1] : value
    s = replace(s, " " => "T")
    return DateTime(s, dateformat"yyyy-mm-ddTHH:MM:SS")
end

# ---------------------------------------------------------------------------
# Public API — mirrors shared/DataLoader.jl function signatures
# ---------------------------------------------------------------------------

"""
    load_xray_flux_real(start_str, end_str) -> NamedTuple

Load real GOES-18 XRS long-wave flux (0.1–0.8 nm) for the given interval.

Parameters
----------
start_str, end_str : ISO date strings "YYYY-MM-DD"

Returns
-------
NamedTuple with fields:
  - `times::Vector{DateTime}` — UTC timestamps (1-minute cadence)
  - `flux::Vector{Float64}`   — X-ray flux in W m⁻² (0.1–0.8 nm channel)
"""
function load_xray_flux_real(start_str::String, end_str::String)
    records = _load_cache("xray_flux", start_str, end_str)
    times = DateTime[]
    flux  = Float64[]
    for r in records
        get(r, :energy, "") == "0.1-0.8nm" || continue
        push!(times, _parse_ts(string(r[:time_tag])))
        push!(flux,  Float64(something(get(r, :flux, NaN), NaN)))
    end
    idx = sortperm(times)
    return (times=times[idx], flux=flux[idx])
end


"""
    load_xray_background_real(start_str, end_str) -> NamedTuple

Load the quiet-Sun X-ray background (12-hour rolling median of longwave flux).

Returns
-------
NamedTuple with fields:
  - `times::Vector{DateTime}`          — UTC timestamps
  - `background_flux::Vector{Float64}` — background flux in W m⁻²
"""
function load_xray_background_real(start_str::String, end_str::String)
    records = _load_cache("xray_background", start_str, end_str)
    times  = DateTime[]
    bg     = Float64[]
    for r in records
        push!(times, _parse_ts(string(r[:time_tag])))
        push!(bg,    Float64(something(get(r, :flux, NaN), NaN)))
    end
    idx = sortperm(times)
    return (times=times[idx], background_flux=bg[idx])
end


"""
    load_magnetometer_real(start_str, end_str) -> NamedTuple

Load the synthetic He magnetometer proxy derived from GOES-18 XRS flux.

He(t) = 100 + (xrs_long − μ) / σ × 10  [nT]

Returns
-------
NamedTuple with fields:
  - `times::Vector{DateTime}` — UTC timestamps
  - `He::Vector{Float64}`     — parallel field proxy (nT)
"""
function load_magnetometer_real(start_str::String, end_str::String)
    records = _load_cache("magnetometer", start_str, end_str)
    times = DateTime[]
    He    = Float64[]
    for r in records
        push!(times, _parse_ts(string(r[:time_tag])))
        val = get(r, :He, NaN)
        push!(He, isnothing(val) ? NaN : Float64(val))
    end
    idx = sortperm(times)
    return (times=times[idx], He=He[idx])
end


"""
    load_euvs_real(start_str, end_str) -> NamedTuple

Load the EUV proxy (shortwave XRS channel used as e_low).

Returns
-------
NamedTuple with fields:
  - `times::Vector{DateTime}`                  — UTC timestamps
  - `channels::Dict{String,Vector{Float64}}`   — irradiance per channel
"""
function load_euvs_real(start_str::String, end_str::String)
    records = _load_cache("euvs", start_str, end_str)
    isempty(records) && return (
        times=DateTime[], channels=Dict{String,Vector{Float64}}()
    )

    _meta = Set(["time_tag", "satellite"])
    sample = records[1]
    channel_keys = [string(k) for k in keys(sample)
                    if !(string(k) in _meta)]

    times   = DateTime[]
    ch_vecs = Dict(k => Float64[] for k in channel_keys)

    for r in records
        push!(times, _parse_ts(string(r[:time_tag])))
        for k in channel_keys
            val = get(r, Symbol(k), NaN)
            push!(ch_vecs[k], isnothing(val) ? NaN : Float64(val))
        end
    end

    idx = sortperm(times)
    sorted_ch = Dict(k => v[idx] for (k, v) in ch_vecs)
    return (times=times[idx], channels=sorted_ch)
end


"""
    load_flare_catalogue_real(start_str, end_str) -> NamedTuple

Load the (empty) flare catalogue for the given real-data interval.

The XRS CSV contains no flare detection; an empty catalogue is returned.

Returns
-------
NamedTuple with fields:
  - `time_begin::Vector{DateTime}`
  - `time_max::Vector{DateTime}`
  - `time_end::Vector{DateTime}`
  - `class_type::Vector{String}`
  - `class_num::Vector{Float64}`
"""
function load_flare_catalogue_real(start_str::String, end_str::String)
    # Always empty for real XRS data (no flare detection applied)
    return (
        time_begin = DateTime[],
        time_max   = DateTime[],
        time_end   = DateTime[],
        class_type = String[],
        class_num  = Float64[],
    )
end

end  # module RealDataLoader
