# Solar Flare Detection — Project Overview

Solar Flare Detection is an educational and computational framework for studying solar
flare phenomena using real observational data from the GOES satellite series.
The project implements the multi-channel instability screening framework
described in *"Detection of Solar Plasma Instabilities Using Multi-Channel
GOES Observations"* (Krüger & Feeney, 2026) — see [PAPER.md](../PAPER.md) and
[CITATIONS.md](../CITATIONS.md).

---

## Four Domains

### 🌀 Spiral Time (`domains/spiral_time/`)

Implements the **phase–memory embedding** ψ(t) = t + iφ(t) + jχ(t) (Eq. 7)
and the **triadic instability operator** ΔΦ(t) = α|ΔS| + β|ΔI| + γ|ΔC|
(Eq. 6). Maps the solar corona to one of four dynamical regimes (Isostasis,
Allostasis, High-Allostasis, Collapse) based on normalized ΔΦ thresholds
(§6.4). The memory coordinate χ(t) captures non-Markovian pre-flare buildup
that amplitude-only monitoring misses.

### ⚡ Energy Transfer (`domains/energy_transfer/`)

Computes the **composite instability indicator** I(t) = w₁ Var_L[X] + w₂
Var_L[B] + w₃ |d/dt EUV| (Eq. 5), integrating X-ray variance, magnetic field
variance, and the EUV time-derivative into a single precursor signal. Connects
to the multi-channel energy distribution across wavelengths during flare onset.

### 🧲 Topology (`domains/topology/`)

Uses GOES magnetometer data to compute the rolling variance Var_L[B](t) (Eq. 3)
and the slow **memory variable** χ(t) as the time-integrated magnetic
variability (§6.3). Captures the structural variability S(t) of coronal
magnetic configuration — the primary driver of free-energy accumulation before
reconnection.

### 💥 Release Events (`domains/release_events/`)

Examines flare initiation, peak flux, and decay using the GOES flare event
catalogue. Implements the **event overlay analysis** (§9.3, Figures 6–8):
overlaying flare timestamps {tₖ} onto rolling-variance and ΔΦ time series to
evaluate precursor lead times and validate the instability screening framework
against observed events.

---

## Navigation

See [how_to_navigate.md](how_to_navigate.md) for the folder structure guide.
See [glossary.md](glossary.md) for definitions of all scientific terms.
