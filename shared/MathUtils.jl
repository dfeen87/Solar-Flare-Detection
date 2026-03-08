"""
MathUtils.jl — Shared Julia mathematical utilities for Solar Flare Detection.

Implements:
  - normalize_01:        Min-max normalization to [0, 1], ignoring NaN values
  - rolling_correlation: Rolling Pearson correlation C(t)  (PAPER.md §6.2)

These functions mirror the relevant parts of `shared/math_utils.py` that are
needed by the Julia pipeline (`tools/run_pipeline.jl`) but were absent from
the Julia side.

All functions are fully implemented.
"""
module MathUtils

export normalize_01, rolling_correlation

# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------

"""
    normalize_01(x::Vector{Float64}) -> Vector{Float64}

Min-max normalize `x` to [0, 1], ignoring NaN values.

If all non-NaN values are identical the function returns a zero vector
(NaN positions are **not** preserved in this case).
If every element is NaN the function returns a copy of the input unchanged.
Otherwise NaN positions are preserved in the output.

Parameters
----------
- `x` — input time series (may contain NaN)

Returns
-------
Vector of values in [0, 1]; NaN positions preserved except when all
non-NaN values are constant (returns all-zeros in that case).

References: PAPER.md — normalization applied before computing ΔΦ(t) (Eq. 6)
and the composite indicator I(t) (Eq. 5).
"""
function normalize_01(x::Vector{Float64})
    valid = filter(!isnan, x)
    if isempty(valid)
        return copy(x)
    end
    lo = minimum(valid)
    hi = maximum(valid)
    if hi == lo
        return zeros(Float64, length(x))
    end
    return (x .- lo) ./ (hi - lo)
end

"""
    rolling_correlation(x::Vector{Float64}, y::Vector{Float64}, L::Int) -> Vector{Float64}

Pearson correlation of `x` and `y` over a rolling window of length `L`.

The first `L-1` values of the output are NaN.  If either window has zero
standard deviation the correlation is set to `0.0`.

This is the cross-channel coherence signal C(t) referenced in PAPER.md §6.2.

Parameters
----------
- `x`, `y` — input time series (must have the same length)
- `L`       — window length (number of data points)

Returns
-------
Vector of rolling Pearson correlation values, same length as inputs.

References: PAPER.md §6.2 — cross-channel coherence C(t).
"""
function rolling_correlation(x::Vector{Float64}, y::Vector{Float64}, L::Int)
    n = length(x)
    out = fill(NaN, n)
    for i in L:n
        wx = x[i-L+1:i]
        wy = y[i-L+1:i]
        sx = _std(wx)
        sy = _std(wy)
        if sx > 0.0 && sy > 0.0
            out[i] = _pearson(wx, wy)
        else
            out[i] = 0.0
        end
    end
    return out
end

# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

function _std(v::AbstractVector{Float64})
    n = length(v)
    m = sum(v) / n
    return sqrt(sum((v .- m).^2) / n)
end

function _pearson(x::AbstractVector{Float64}, y::AbstractVector{Float64})
    n  = length(x)
    mx = sum(x) / n
    my = sum(y) / n
    num   = sum((x .- mx) .* (y .- my))
    denom = sqrt(sum((x .- mx).^2) * sum((y .- my).^2))
    denom == 0.0 && return 0.0
    return num / denom
end

end  # module MathUtils
