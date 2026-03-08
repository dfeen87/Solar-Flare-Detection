# 🧲 Topology Domain

## Purpose

The `topology` domain studies the **magnetic field variability** of the corona
using GOES magnetometer data, computing the rolling variance Var_L[B](t) and
the slow **memory variable** χ(t) described in PAPER.md §6.3.

## Key Constructs

### Rolling Variance of B(t) — PAPER.md Eq. (3)

```
Var_L[B](t) = (1/L) Σ_{i=0}^{L-1} (B(t-i) - B̄_L(t))²
```

This serves as the **structural variability** component S(t) in the triadic
operator ΔΦ(t).

### Memory Variable χ(t) — PAPER.md §6.3

```
χ(t) ≈ ∫₀ᵗ Var_L[B](τ) dτ
```

> "χ(t) may be approximated by time-integrated magnetic variability measures."
> — PAPER.md §6.3

The cumulative integral encodes the **accumulated magnetic stress** in active
regions, capturing the non-Markovian memory of the pre-flare corona.

## Data

- Source: GOES magnetometer — fetched via `shared/data_loader.py` (`magnetometers-7-day.json`)
- Channel: He (parallel component) — the most relevant proxy for B(t)

## Running the Example

```bash
# From the repo root:
pip install -r requirements.txt
python domains/topology/examples_python/magnetometer_variance_demo.py
```

Output figure is saved to `examples_python/output/magnetometer_variance_demo.png`.

## Julia Module

High-performance stubs live in `tools/topology/Topology.jl`.
