# ⚡ Energy Transfer Domain

## Purpose

The `energy_transfer` domain implements the **composite instability indicator**
I(t) from *Krüger & Feeney (2026)*, which integrates X-ray variance, magnetic
field variance, and the EUV time-derivative into a single precursor signal.

## Key Constructs

### Rolling Variance — PAPER.md Eq. (3)

```
Var_L[X](t) = (1/L) Σ_{i=0}^{L-1} (X(t-i) - X̄_L(t))²
```

Applied to both the X-ray flux X(t) and the magnetometer field proxy B(t).

### Composite Indicator — PAPER.md Eq. (5)

```
I(t) = w₁ Var_L[X](t) + w₂ Var_L[B](t) + w₃ |d/dt EUV(t)|
```

| Term | Physical Meaning |
|------|-----------------|
| Var_L[X](t) | Short-timescale X-ray flux fluctuations |
| Var_L[B](t) | Magnetic field variability proxy |
| \|d/dt EUV(t)\| | Rate of change in extreme ultraviolet output |

> **Note:** Default weights w₁ = w₂ = w₃ = 1/3 (equal weighting). PAPER.md
> §5 states these are calibrated from historical flare catalogues. Each
> component is normalized to [0, 1] before combining.

## Running the Example

```bash
# From the repo root:
pip install -r requirements.txt
python domains/energy_transfer/examples_python/composite_indicator_demo.py
```

Output figure is saved to `examples_python/output/composite_indicator_demo.png`.

## Julia Module

High-performance stubs live in `tools/energy_transfer/EnergyTransfer.jl`.
