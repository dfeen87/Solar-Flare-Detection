"""
Topology.jl — Julia module for magnetic topology analysis.

Implements:
  - rolling_variance_B:  Var_L[B](t) applied to magnetometer data  (PAPER.md Eq. 3)
  - compute_chi:         χ(t) = ∫ Var_L[B] dt (cumulative integral) (PAPER.md §6.3)
  - MemoryState:         container for the χ(t) memory variable

All function bodies are stubs pending full implementation.
"""
module Topology

export MemoryState, rolling_variance_B, compute_chi

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

"""
    MemoryState

Container for the memory variable χ(t) (PAPER.md §6.3).

Fields
------
- `chi::Float64` — cumulative integral of Var_L[B], representing accumulated
                   magnetic stress in active regions.

References: PAPER.md §6.3.
"""
struct MemoryState
    chi::Float64
end

# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------

"""
    rolling_variance_B(B::Vector{Float64}, L::Int) -> Vector{Float64}

Compute the rolling variance Var_L[B](t) of magnetometer B(t):

    Var_L[B](t) = (1/L) Σ_{i=0}^{L-1} (B(t-i) - B̄_L(t))²

Used as the structural variability component S(t) in ΔΦ(t).

Parameters
----------
- `B` — magnetometer He-component time series
- `L` — window length (number of data points)

Returns
-------
Vector of rolling-variance values; first L-1 entries are NaN.

References: PAPER.md Eq. (3); §6.2 S(t) proxy definition.
"""
function rolling_variance_B(B::Vector{Float64}, L::Int)
    error("Not yet implemented")
end

"""
    compute_chi(var_B::Vector{Float64}, dt::Float64) -> Vector{Float64}

Compute the memory variable χ(t) as the cumulative trapezoidal integral of
Var_L[B](t):

    χ(t) ≈ ∫₀ᵗ Var_L[B](τ) dτ

PAPER.md §6.3: "χ(t) may be approximated by time-integrated magnetic
variability measures."

Parameters
----------
- `var_B` — rolling variance of magnetometer B(t)
- `dt`    — time step in seconds between consecutive samples

Returns
-------
Vector of χ(t) values (cumulative integral), same length as `var_B`.

References: PAPER.md §6.3; Eq. (7) for role in ψ(t).
"""
function compute_chi(var_B::Vector{Float64}, dt::Float64)
    error("Not yet implemented")
end

end  # module Topology
