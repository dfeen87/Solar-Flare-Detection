#!/usr/bin/env julia
# run_pipeline.jl — End-to-end Julia analysis pipeline for Solar Flare Detection.
#
# Wires together all five Julia modules into a complete analysis pipeline,
# producing summary statistics for each processing step.
#
# Usage:
#   julia tools/run_pipeline.jl
#
# Steps:
#   1. Load data          — X-ray flux, magnetometer, EUVS, flare catalogue
#   2. Rolling variances  — Var_L[X](t) and Var_L[B](t)
#   3. Composite I(t)     — normalize components, combine via EnergyTransfer
#   4. ΔΦ(t) and regimes  — coherence C(t), triadic operator, classification
#   5. ψ(t) embedding     — χ(t) memory variable, phase–memory states
#   6. Lead-time analysis — precursor peaks vs. flare catalogue

# ---------------------------------------------------------------------------
# Bootstrap: add shared/ and tool subdirectories to LOAD_PATH
# ---------------------------------------------------------------------------

const _PIPELINE_DIR = @__DIR__
const _REPO_ROOT    = dirname(_PIPELINE_DIR)

for _p in [
    joinpath(_REPO_ROOT, "shared"),
    joinpath(_REPO_ROOT, "tools", "energy_transfer"),
    joinpath(_REPO_ROOT, "tools", "topology"),
    joinpath(_REPO_ROOT, "tools", "spiral_time"),
    joinpath(_REPO_ROOT, "tools", "release_events"),
]
    _p ∉ LOAD_PATH && push!(LOAD_PATH, _p)
end

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

include(joinpath(_REPO_ROOT, "shared",                      "MathUtils.jl"))
include(joinpath(_REPO_ROOT, "shared",                      "DataLoader.jl"))
include(joinpath(_REPO_ROOT, "tools", "energy_transfer",    "EnergyTransfer.jl"))
include(joinpath(_REPO_ROOT, "tools", "topology",           "Topology.jl"))
include(joinpath(_REPO_ROOT, "tools", "spiral_time",        "SpiralTime.jl"))
include(joinpath(_REPO_ROOT, "tools", "release_events",     "ReleaseEvents.jl"))

using .MathUtils
using .DataLoader
using .EnergyTransfer
using .Topology
using .SpiralTime
using .ReleaseEvents
using Dates

# ---------------------------------------------------------------------------
# Pipeline constants
# ---------------------------------------------------------------------------

const L  = 30      # Rolling window length (data points; = 30 min at 1-min cadence)
const dt = 60.0    # GOES 1-minute cadence (seconds)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

function _mean_valid(v)
    valid = filter(!isnan, v)
    isempty(valid) ? NaN : sum(valid) / length(valid)
end

# ---------------------------------------------------------------------------
# Step 1 — Load data
# ---------------------------------------------------------------------------

println("=" ^ 60)
println("Solar Flare Detection — Julia Pipeline")
println("=" ^ 60)
println("\n[Step 1] Loading GOES observational data...")

xray   = DataLoader.load_xray_flux()
mag    = DataLoader.load_magnetometer()
euvs   = DataLoader.load_euvs()
flares = DataLoader.load_xray_flares()

println("  X-ray flux   : $(length(xray.flux)) samples  ($(xray.times[1]) → $(xray.times[end]))")
println("  Magnetometer : $(length(mag.He)) samples")
println("  EUVS channels: $(length(euvs.channels)) channel(s)")
println("  Flare events : $(length(flares.time_begin)) events")

# Pick the first available EUV channel for analysis
euv_key = first(keys(euvs.channels))
euv_raw = euvs.channels[euv_key]
println("  Using EUV channel: $euv_key")

# Align all time series to the shortest common length
N    = min(length(xray.flux), length(mag.He), length(euv_raw))
flux = xray.flux[1:N]
B    = mag.He[1:N]
euv  = euv_raw[1:N]
println("  Aligned to N = $N samples")

# ---------------------------------------------------------------------------
# Step 2 — Rolling variances Var_L[X](t) and Var_L[B](t)
# ---------------------------------------------------------------------------

println("\n[Step 2] Computing rolling variances (L = $L)...")

var_x = EnergyTransfer.rolling_variance(flux, L)
var_b = Topology.rolling_variance_B(B, L)

println("  Var_L[X](t) : $(count(!isnan, var_x)) valid values  " *
        "(mean = $(round(_mean_valid(var_x), digits=6)))")
println("  Var_L[B](t) : $(count(!isnan, var_b)) valid values  " *
        "(mean = $(round(_mean_valid(var_b), digits=6)))")

# ---------------------------------------------------------------------------
# Step 3 — Composite indicator I(t)
# ---------------------------------------------------------------------------

println("\n[Step 3] Computing composite indicator I(t)...")

d_euv      = EnergyTransfer.euv_derivative(euv, dt)
var_x_norm = MathUtils.normalize_01(var_x)
var_b_norm = MathUtils.normalize_01(var_b)
d_euv_norm = MathUtils.normalize_01(d_euv)

indicator  = EnergyTransfer.composite_indicator(var_x_norm, var_b_norm, d_euv_norm)
valid_I    = filter(!isnan, indicator)

println("  I(t) : $(length(valid_I)) valid values")
if !isempty(valid_I)
    println("         min = $(round(minimum(valid_I),  digits=4))  " *
            "max = $(round(maximum(valid_I),  digits=4))  " *
            "mean = $(round(sum(valid_I)/length(valid_I), digits=4))")
end

# ---------------------------------------------------------------------------
# Step 4 — ΔΦ(t) and regime classification
# ---------------------------------------------------------------------------

println("\n[Step 4] Computing ΔΦ(t) and regime classification...")

C             = MathUtils.rolling_correlation(flux, euv, L)
delta_phi     = SpiralTime.compute_delta_phi(var_b_norm, indicator, C)
delta_phi_norm = MathUtils.normalize_01(delta_phi)

# Classify the most recent valid timestep
last_idx = findlast(!isnan, delta_phi_norm)
if last_idx !== nothing
    current = SpiralTime.classify_regime(delta_phi_norm[last_idx])
    println("  Current regime : $(current.regime)  " *
            "(ΔΦ_norm = $(round(delta_phi_norm[last_idx], digits=4)))")
else
    println("  Current regime : unable to classify (all NaN)")
end

# Regime distribution over the entire time series
valid_phi = filter(!isnan, delta_phi_norm)
if !isempty(valid_phi)
    n_total = length(valid_phi)
    n_iso   = count(v -> v < 0.15,          valid_phi)
    n_allo  = count(v -> 0.15 <= v < 0.35,  valid_phi)
    n_high  = count(v -> 0.35 <= v < 0.40,  valid_phi)
    n_coll  = count(v -> v >= 0.40,          valid_phi)
    println("  Regime distribution ($n_total valid samples):")
    println("    Isostasis       : $n_iso  ($(round(100n_iso /n_total, digits=1))%)")
    println("    Allostasis      : $n_allo  ($(round(100n_allo/n_total, digits=1))%)")
    println("    High-Allostasis : $n_high  ($(round(100n_high/n_total, digits=1))%)")
    println("    Collapse        : $n_coll  ($(round(100n_coll/n_total, digits=1))%)")
end

# ---------------------------------------------------------------------------
# Step 5 — Phase–memory embedding ψ(t)
# ---------------------------------------------------------------------------

println("\n[Step 5] Computing phase–memory embedding ψ(t)...")

chi_vec = Topology.compute_chi(var_b, dt)

# Sample the last (up to 5) valid points for display
sample_indices = findall(!isnan, delta_phi_norm)
sample_indices = sample_indices[max(1, end - 4):end]

psi_states = PhaseMemoryState[]
for idx in sample_indices
    t_val   = Float64(idx) * dt
    phi_val = isnan(delta_phi_norm[idx]) ? 0.0 : delta_phi_norm[idx]
    chi_val = isnan(chi_vec[idx])        ? 0.0 : chi_vec[idx]
    push!(psi_states, SpiralTime.compute_psi(t_val, phi_val, chi_val))
end

println("  Sampled $(length(psi_states)) ψ(t) state(s):")
for s in psi_states
    println("    ψ : t = $(round(s.t, digits=1)) s  " *
            "φ = $(round(s.phi, digits=4))  " *
            "χ = $(round(s.chi, digits=6))")
end

# ---------------------------------------------------------------------------
# Step 6 — Lead-time analysis
# ---------------------------------------------------------------------------

println("\n[Step 6] Lead-time analysis...")

if length(flares.time_begin) > 0
    times_aligned    = xray.times[1:N]
    indicator_peaks  = (times = times_aligned, values = indicator)

    lead_times   = ReleaseEvents.compute_lead_times(flares.time_max, indicator_peaks)
    valid_leads  = filter(!isnan, lead_times)

    println("  Flare events analysed : $(length(lead_times))")
    println("  Events with precursor : $(length(valid_leads))")
    if !isempty(valid_leads)
        println("  Lead-time statistics  :")
        println("    min  = $(round(minimum(valid_leads) / 60.0, digits=1)) min")
        println("    max  = $(round(maximum(valid_leads) / 60.0, digits=1)) min")
        println("    mean = $(round(sum(valid_leads) / length(valid_leads) / 60.0, digits=1)) min")
    end
else
    println("  No flare events in catalogue — skipping lead-time analysis.")
end

println("\n" * "=" ^ 60)
println("Pipeline complete.")
println("=" ^ 60)
