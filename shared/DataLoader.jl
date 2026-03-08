"""
DataLoader.jl — Julia data loading module for Solar Flare Detection.

Mirrors the functionality of shared/data_loader.py, loading observational
GOES data from local JSON cache files or, when those files are absent,
fetching them from the NOAA Space Weather Prediction Center (SWPC) REST API.

Data sources (PAPER.md §4.1, Table 1):
  - GOES X-ray flux          assets/data/xray/xrays-7-day.json
  - GOES flare catalogue     assets/data/xray/xray-flares-7-day.json
  - GOES X-ray background    assets/data/xray/xray-background-7-day.json
  - GOES magnetometer        assets/data/magnetometers/magnetometers-7-day.json
  - GOES EUVS irradiance     assets/data/euvs/euvs-7-day.json

Dependencies: JSON3 (parsing), Downloads (stdlib, NOAA fallback), Dates (stdlib).

References
----------
PAPER.md §4.1, Table 1 — observational channels and physical interpretations.
"""
module DataLoader

using Dates
using Downloads
using JSON3

export load_xray_flux, load_xray_flares, load_magnetometer, load_euvs

# ---------------------------------------------------------------------------
# Paths and NOAA URLs
# ---------------------------------------------------------------------------

const _REPO_ROOT = joinpath(@__DIR__, "..")
const _DATA_ROOT = joinpath(_REPO_ROOT, "assets", "data")

const _SOURCES = Dict(
    "xray"       => ("xray/xrays-7-day.json",
                     "https://services.swpc.noaa.gov/json/goes/primary/xrays-7-day.json"),
    "flares"     => ("xray/xray-flares-7-day.json",
                     "https://services.swpc.noaa.gov/json/goes/primary/xray-flares-7-day.json"),
    "background" => ("xray/xray-background-7-day.json",
                     "https://services.swpc.noaa.gov/json/goes/primary/xray-background-7-day.json"),
    "magneto"    => ("magnetometers/magnetometers-7-day.json",
                     "https://services.swpc.noaa.gov/json/goes/primary/magnetometers-7-day.json"),
    "euvs"       => ("euvs/euvs-7-day.json",
                     "https://services.swpc.noaa.gov/json/goes/primary/euvs-7-day.json"),
)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

"""
    _load_json(key) -> JSON3 array

Return parsed JSON for *key* using the local cache file first; falls back to
the NOAA SWPC REST API if the local file is absent.
"""
function _load_json(key::String)
    local_rel, url = _SOURCES[key]
    local_path = joinpath(_DATA_ROOT, local_rel)

    if isfile(local_path)
        return JSON3.read(read(local_path, String))
    end

    # Fallback: fetch from NOAA SWPC
    buf = IOBuffer()
    try
        Downloads.download(url, buf)
    catch exc
        error("Local file '$local_path' not found and NOAA fetch failed: $exc")
    end
    return JSON3.read(String(take!(buf)))
end


"""
    _parse_ts(value) -> DateTime

Parse an ISO-8601-like timestamp string into a `DateTime`.  Handles the three
NOAA formats: ``"2025-01-15T12:34:00Z"``, ``"2025-01-15T12:34:00"``, and
``"2025-01-15 12:34:00"``.
"""
function _parse_ts(value::Union{String, AbstractString})
    # Strip trailing Z
    s = endswith(value, "Z") ? value[1:end-1] : value
    # Replace space separator with T for DateTime parsing
    s = replace(s, " " => "T")
    return DateTime(s, dateformat"yyyy-mm-ddTHH:MM:SS")
end

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

"""
    load_xray_flux() -> NamedTuple

Load GOES X-ray flux (0.1–0.8 nm channel).

Returns a NamedTuple with fields:
  - `times::Vector{DateTime}` — measurement timestamps
  - `flux::Vector{Float64}`   — X-ray flux in W m⁻² (0.1–0.8 nm)

References: PAPER.md §4.1, Table 1 — X(t) channel.
"""
function load_xray_flux()
    records = _load_json("xray")
    times = DateTime[]
    flux  = Float64[]
    for r in records
        get(r, :energy, "") == "0.1-0.8nm" || continue
        push!(times, _parse_ts(r[:time_tag]))
        push!(flux,  something(get(r, :flux, NaN), NaN) |> Float64)
    end
    idx = sortperm(times)
    return (times=times[idx], flux=flux[idx])
end


"""
    load_xray_flares() -> NamedTuple

Load GOES flare event catalogue.

Returns a NamedTuple with fields:
  - `time_begin::Vector{DateTime}` — flare start times
  - `time_max::Vector{DateTime}`   — peak times
  - `time_end::Vector{DateTime}`   — end times
  - `class_type::Vector{String}`   — GOES class letter (A, B, C, M, X)
  - `class_num::Vector{Float64}`   — numeric class qualifier

References: PAPER.md §4.1, Table 1 — flare event catalogue {tₖ}.
"""
function load_xray_flares()
    records = _load_json("flares")
    time_begin = DateTime[]
    time_max   = DateTime[]
    time_end   = DateTime[]
    class_type = String[]
    class_num  = Float64[]

    for r in records
        class_str = string(get(r, :class, ""))
        ct = isempty(class_str) ? "" : string(class_str[1])
        cn = length(class_str) > 1 ? tryparse(Float64, SubString(class_str, 2)) : nothing
        push!(time_begin, _parse_ts(string(get(r, :begin_time, ""))))
        push!(time_max,   _parse_ts(string(get(r, :max_time, ""))))
        push!(time_end,   _parse_ts(string(get(r, :end_time, ""))))
        push!(class_type, ct)
        push!(class_num,  isnothing(cn) ? NaN : cn)
    end

    idx = sortperm(time_begin)
    return (
        time_begin = time_begin[idx],
        time_max   = time_max[idx],
        time_end   = time_end[idx],
        class_type = class_type[idx],
        class_num  = class_num[idx],
    )
end


"""
    load_magnetometer() -> NamedTuple

Load GOES magnetometer (He parallel component) data.

Returns a NamedTuple with fields:
  - `times::Vector{DateTime}` — timestamps
  - `He::Vector{Float64}`     — parallel magnetic field component (nT)

References: PAPER.md §4.1, Table 1 — B(t) channel; §6.2 S(t) proxy.
"""
function load_magnetometer()
    records = _load_json("magneto")
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
    load_euvs() -> NamedTuple

Load GOES EUVS irradiance data.  All numeric channels present in the JSON are
returned.

Returns a NamedTuple with fields:
  - `times::Vector{DateTime}`      — timestamps
  - `channels::Dict{String,Vector{Float64}}` — irradiance per channel

References: PAPER.md §4.1, Table 1 — EUV(t) channel; §6.2 C(t) proxy.
"""
function load_euvs()
    records = _load_json("euvs")
    isempty(records) && return (times=DateTime[], channels=Dict{String,Vector{Float64}}())

    _meta = Set(["time_tag", "satellite", "flux"])
    sample = records[1]
    channel_keys = [string(k) for k in keys(sample)
                    if !(string(k) in _meta) && isa(sample[k], Union{Number, Nothing})]

    times    = DateTime[]
    ch_vecs  = Dict(k => Float64[] for k in channel_keys)

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

end  # module DataLoader
