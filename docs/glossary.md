# Solarflare — Scientific Glossary

Definitions of key scientific and mathematical terms used throughout the
Solarflare repository and the associated paper (Krüger & Feeney, 2026).

---

## Magnetic Reconnection

A fundamental plasma-physics process in which oppositely directed magnetic
field lines converge at an **X-point**, break, and reconnect in a new
topology. The stored magnetic free energy is converted into plasma heating,
electromagnetic radiation (X-ray and EUV), and kinetic energy of accelerated
particles. Magnetic reconnection is the primary energy-release mechanism of
solar flares.

*See:* Priest & Forbes (2002); PAPER.md §2.

---

## Coronal Loop

An arched magnetic flux tube anchored at both ends in the photosphere (the
visible solar surface). Coronal loops are the primary sites of free-energy
storage and flare onset. Convective motions at the footpoints continuously
braid and stress the field lines, building up magnetic free energy over hours
to days before reconnection releases it.

*See:* Aschwanden (2019); PAPER.md §2.

---

## Rolling Variance — Var_L[X](t)

A sliding-window variance estimator used as a pre-flare instability proxy:

    Var_L[X](t) = (1/L) Σ_{i=0}^{L-1} (X(t-i) − X̄_L(t))²

Captures short-timescale fluctuations in the X-ray flux X(t) that increase
before flare onset, while suppressing the long-term trend.

*See:* PAPER.md Eq. (3).

---

## Triadic Instability Operator — ΔΦ(t)

A composite functional that integrates three complementary signal dimensions:

    ΔΦ(t) = α |ΔS(t)| + β |ΔI(t)| + γ |ΔC(t)|

where ΔS, ΔI, ΔC are first differences of the structural, informational, and
coherence components respectively. Weights α, β, γ are calibrated from
historical flare catalogues (equal 1/3 weighting used as placeholder).

*See:* PAPER.md Eq. (6); §6.2.

---

## Composite Indicator — I(t)

A weighted combination of three observational channels that serves as the
primary precursor signal:

    I(t) = w₁ Var_L[X](t) + w₂ Var_L[B](t) + w₃ |d/dt EUV(t)|

Each component is normalized to [0, 1] before combining. Weights are
calibrated from historical data.

*See:* PAPER.md Eq. (5).

---

## Phase–Memory Embedding — ψ(t)

A structured phase–memory coordinate system into which observed signals are
embedded:

    ψ(t) = t + i φ(t) + j χ(t)

where φ(t) is a phase-coherence coordinate (cross-channel coupling between
EUV and X-ray) and χ(t) is the slow memory variable. The non-Markovian
structure enables sensitivity to **coherence degradation** and **temporal
acceleration** — early precursors of flare onset that amplitude-only monitoring
misses.

*See:* PAPER.md Eq. (7).

---

## Memory Variable — χ(t)

A slow, cumulative variable encoding the accumulated magnetic stress in active
regions:

    χ(t) ≈ ∫₀ᵗ Var_L[B](τ) dτ

χ(t) captures the non-Markovian history of the pre-flare corona. It increases
monotonically as magnetic free energy builds up, providing a long-horizon
precursor signal.

*See:* PAPER.md §6.3.

---

## Isostasis

The quietest dynamical regime, characterized by ΔΦ < 0.15 (after
normalization). The corona is in energy balance; magnetic free energy is at
background levels. No flare onset is imminent.

*See:* PAPER.md §6.4.

---

## Allostasis

An intermediate stress regime: 0.15 ≤ ΔΦ < 0.35. Progressive magnetic stress
accumulation is occurring. The corona is adapting to increasing free energy;
flare risk is elevated but below the critical threshold.

*See:* PAPER.md §6.4.

---

## High-Allostasis

A critical instability-buildup regime: 0.35 ≤ ΔΦ < 0.40. The corona is near
the reconnection threshold. Precursor signatures should be visible across
multiple observational channels. Immediate flare risk is high.

*See:* PAPER.md §6.4.

---

## Collapse (Flare)

The reconnection/flare regime: ΔΦ ≥ 0.40. Magnetic reconnection has been
triggered; free energy is being rapidly released as X-ray and EUV radiation.
This corresponds to the observed flare event.

*See:* PAPER.md §6.4.

---

## Non-Markovian Dynamics

System behavior in which future evolution depends not only on the current
state but also on the **history** of past states. The pre-flare corona is
non-Markovian because magnetic free energy can accumulate for hours or days
before reconnection is triggered. This memory effect is captured by χ(t) and
is the key reason amplitude-only (instantaneous) monitoring is insufficient
for early warning.

*See:* PAPER.md §3, §6.3.

---

## Self-Organized Criticality (SOC)

A statistical property of complex systems in which the system naturally evolves
toward a critical state — without external tuning — from which it exhibits
scale-free (power-law) responses. Solar flare energies follow a power-law
distribution P(E) ∝ E^{-α}, consistent with SOC. This avalanche-like behavior
is the core statistical structure exploited by the instability screening
framework.

*See:* PAPER.md §2; Aschwanden (2019).
