"""
EnergyTransfer.jl — Julia module for composite instability indicator I(t).

Implements:
  - rolling_variance:      Var_L[X](t) per PAPER.md Eq. (3)
  - composite_indicator:   I(t) = w₁ Var_L[X] + w₂ Var_L[B] + w₃ |d/dt EUV|  (Eq. 5)
  - euv_derivative:        |d/dt EUV(t)| via finite differences

All functions are fully implemented.
"""
module EnergyTransfer

export rolling_variance, composite_indicator, euv_derivative

# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------

"""
    rolling_variance(x::Vector{Float64}, L::Int) -> Vector{Float64}

Compute the rolling variance Var_L[X](t) over a sliding window of length L:

    Var_L[X](t) = (1/L) Σ_{i=0}^{L-1} (X(t-i) - X̄_L(t))²

The first L-1 values of the output are NaN (window not yet full).

Parameters
----------
- `x` — input time series
- `L` — window length (number of data points)

Returns
-------
Vector of rolling-variance values, same length as `x`.

References: PAPER.md Eq. (3).
"""
function rolling_variance(x::Vector{Float64}, L::Int)
    n = length(x)
    out = fill(NaN, n)
    for i in L:n
        window = x[i-L+1:i]
        m = sum(window) / L
        out[i] = sum((window .- m).^2) / L
    end
    return out
end

"""
    composite_indicator(var_x, var_b, d_euv; w1=1/3, w2=1/3, w3=1/3) -> Vector{Float64}

Compute the composite instability indicator I(t) per PAPER.md Eq. (5):

    I(t) = w₁ Var_L[X](t) + w₂ Var_L[B](t) + w₃ |d/dt EUV(t)|

Each component should be normalized to [0, 1] before calling this function
so that the weights are physically meaningful.

Parameters
----------
- `var_x`  — rolling variance of X-ray flux (normalized to [0,1])
- `var_b`  — rolling variance of magnetometer B (normalized to [0,1])
- `d_euv`  — |d/dt EUV(t)| (normalized to [0,1])
- `w1`, `w2`, `w3` — weights (default 1/3 each; calibrate from flare catalogues)

Returns
-------
Vector of I(t) values in [0, 1].

References: PAPER.md Eq. (5).
"""
function composite_indicator(var_x, var_b, d_euv; w1=1/3, w2=1/3, w3=1/3)
    return w1 .* var_x .+ w2 .* var_b .+ w3 .* d_euv
end

"""
    euv_derivative(euv::Vector{Float64}, dt::Float64) -> Vector{Float64}

Compute |d/dt EUV(t)| via central finite differences.

    |d/dt EUV(t)| ≈ |EUV(t+dt) - EUV(t-dt)| / (2 dt)

Endpoints use one-sided differences.

Parameters
----------
- `euv` — EUV irradiance time series
- `dt`  — time step in seconds

Returns
-------
Vector of |d/dt EUV| values, same length as `euv`.

References: PAPER.md Eq. (5) — third term.
"""
function euv_derivative(euv::Vector{Float64}, dt::Float64)
    n = length(euv)
    out = Vector{Float64}(undef, n)
    if n == 1
        out[1] = 0.0
        return out
    end
    # One-sided forward difference for first point
    out[1] = abs((euv[2] - euv[1]) / dt)
    # Central differences for interior points
    for i in 2:n-1
        out[i] = abs((euv[i+1] - euv[i-1]) / (2 * dt))
    end
    # One-sided backward difference for last point
    out[n] = abs((euv[n] - euv[n-1]) / dt)
    return out
end

end  # module EnergyTransfer
