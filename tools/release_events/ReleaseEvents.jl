"""
ReleaseEvents.jl — Julia module for flare event analysis.

Implements:
  - FlareEvent:       struct representing a catalogued GOES flare event
  - compute_lead_times: lead-time analysis comparing precursor peaks to flare onset
  - overlay_events:   prepare event overlay data for visualization

All function bodies are stubs pending full implementation.
"""
module ReleaseEvents

using Dates

export FlareEvent, compute_lead_times, overlay_events

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

"""
    FlareEvent

Represents a catalogued GOES flare event.

Fields
------
- `time::DateTime`       — flare peak time (time_max in NOAA catalogue)
- `class_type::String`   — GOES class letter (\"A\", \"B\", \"C\", \"M\", \"X\")
- `peak_flux::Float64`   — peak X-ray flux in W m⁻²

References: PAPER.md §9.3 — event catalogue {tₖ}.
"""
struct FlareEvent
    time::DateTime
    class_type::String
    peak_flux::Float64
end

# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------

"""
    compute_lead_times(flare_times, indicator_peaks) -> Vector{Float64}

Compute lead times between precursor indicator peaks and flare onset times.

For each flare event in `flare_times`, find the most recent local maximum in
`indicator_peaks` that precedes the flare onset, and return the time difference
as the lead time.

Parameters
----------
- `flare_times`     — vector of DateTime values for flare onsets
- `indicator_peaks` — NamedTuple or similar with fields `times` and `values`
                      representing the precursor indicator time series

Returns
-------
Vector of lead times (in seconds) for each flare event. NaN if no precursor
peak is found before the event.

References: PAPER.md §9.3 — lead-time analysis.
"""
function compute_lead_times(flare_times, indicator_peaks)
    error("Not yet implemented")
end

"""
    overlay_events(timeseries, flare_events) -> NamedTuple

Prepare event overlay data for visualization: pair each catalogued flare event
with the corresponding segment of the indicator time series for plotting.

Parameters
----------
- `timeseries`    — NamedTuple with fields `times::Vector{DateTime}` and
                    `values::Vector{Float64}` for the precursor indicator
- `flare_events`  — vector of `FlareEvent`

Returns
-------
NamedTuple with fields:
  - `series`  — the input `timeseries`
  - `events`  — the input `flare_events`
  - `classes` — vector of class letter strings (for colour coding)

References: PAPER.md §9.3, Figures 6–8.
"""
function overlay_events(timeseries, flare_events)
    error("Not yet implemented")
end

end  # module ReleaseEvents
