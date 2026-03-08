# 🌀 Spiral Time Domain

## Purpose

The `spiral_time` domain implements the **phase–memory embedding** ψ(t) and the
**triadic instability operator** ΔΦ(t) from *Krüger & Feeney (2026)*.

These constructs capture the non-Markovian, memory-dependent dynamics of the
pre-flare corona that amplitude-only monitoring misses.

## Key Constructs

### Phase–Memory Embedding — PAPER.md Eq. (7)

```
ψ(t) = t + i φ(t) + j χ(t)
```

| Symbol | Meaning |
|--------|---------|
| φ(t)  | Phase-coherence coordinate (rolling X-ray / EUV correlation) |
| χ(t)  | Slow memory variable (cumulative magnetic variability — §6.3) |

### Triadic Instability Operator — PAPER.md Eq. (6)

```
ΔΦ(t) = α|ΔS(t)| + β|ΔI(t)| + γ|ΔC(t)|
```

| Component | Proxy | Physical Meaning |
|-----------|-------|------------------|
| S(t) | Var_L[B](t) | Structural variability (magnetometer rolling variance) |
| I(t) | Var_L[X](t) | Informational complexity (X-ray rolling variance) |
| C(t) | corr(X, EUV) | Cross-channel coherence |

### Regime Classification — PAPER.md §6.4

| Regime | ΔΦ (normalized) |
|--------|-----------------|
| 🟢 Isostasis | < 0.15 |
| 🟡 Allostasis | 0.15 – 0.35 |
| 🟠 High-Allostasis | 0.35 – 0.40 |
| 🔴 Collapse | ≥ 0.40 |

## Running the Example

```bash
# From the repo root:
pip install -r requirements.txt
python domains/spiral_time/examples_python/variance_and_regime_demo.py
```

Output figure is saved to `examples_python/output/variance_and_regime_demo.png`.

## Julia Module

High-performance stubs live in `tools/spiral_time/SpiralTime.jl`.
