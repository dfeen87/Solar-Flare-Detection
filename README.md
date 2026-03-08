[![CI](https://github.com/dfeen87/Solar-Flare-Detection/actions/workflows/ci.yml/badge.svg)](https://github.com/dfeen87/Solar-Flare-Detection/actions/workflows/ci.yml)
[![Python Tests](https://github.com/dfeen87/Solar-Flare-Detection/actions/workflows/python-tests.yml/badge.svg)](https://github.com/dfeen87/Solar-Flare-Detection/actions/workflows/python-tests.yml)
[![Julia Tests](https://github.com/dfeen87/Solar-Flare-Detection/actions/workflows/julia-tests.yml/badge.svg)](https://github.com/dfeen87/Solar-Flare-Detection/actions/workflows/julia-tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/dfeen87/Solar-Flare-Detection/blob/main/LICENSE)

# ☀️ Solar Flare Detection

Domain‑based solar physics repository combining Python examples with Julia models.  
Uses real GOES X‑ray, EUV, and magnetometer data to explore flare behavior, energy release, magnetic topology, and instability dynamics through clear theory, visuals, and reproducible tools.

> **Research basis:** This repository implements and extends the multi-channel instability screening framework described in *"Detection of Solar Plasma Instabilities Using Multi-Channel GOES Observations"* (Krüger & Feeney, 2026).

---

## Overview

Solar Flare Detection is an educational and computational framework for studying solar flare phenomena using real observational data. The repository separates **didactic Python examples** from **high‑performance Julia models**, allowing users to learn the concepts and then explore deeper numerical simulations.

Solar flares occur when magnetic energy stored in the corona is rapidly released through **magnetic reconnection** — converting stored magnetic free energy into plasma heating, electromagnetic radiation, and kinetic energy of accelerated particles. Major flares and associated coronal mass ejections (CMEs) can disrupt satellite operations, navigation systems, communication infrastructure, and in extreme cases even power grids.

All datasets are sourced from GOES and EUVS instruments and fetched at runtime from the NOAA SWPC API via `shared/data_loader.py`.

---

## Physical Background

### The Solar Flare Mechanism

Magnetic activity originates from convective plasma motions deep inside the Sun. These motions generate and twist magnetic field lines that rise buoyantly through the photosphere and form **coronal loop structures** — the primary sites of flare energy storage and release.

```
                         ↑  Outflow Jet
                         │
          ←←←←←←←←←←←─ ┼ ─→→→→→→→→→→→
         ╲               │               ╱
          ╲   ←←    ─────●─────    →→   ╱
           ╲          X-point          ╱
           ╱       (reconnection)      ╲
          ╱   →→    ─────●─────    ←←   ╲
         ╱               │               ╲
          →→→→→→→→→→→→─ ┼ ─←←←←←←←←←←←
                         │
                         ↓  Outflow Jet
              ┌───────────────────────────┐
              │  Magnetic Reconnection    │
              │        Region             │
              └───────────────────────────┘
```

As magnetic stress accumulates in coronal loops, the system approaches a **critical instability threshold**. Flare energies follow a power-law distribution consistent with self-organized criticality:

> 𝑃(𝐸) ∝ 𝐸⁻ᵅ

This avalanche-like behavior — where gradual magnetic stress leads to sudden, large-scale energy release — is the core physical phenomenon this repository investigates.

### The Pre-Flare Build-Up

A key insight driving this framework is that the pre-flare corona is **non-Markovian**: magnetic energy can accumulate for hours or days before reconnection releases it. This memory effect means precursor signatures exist *before* the flare itself, embedded in the statistical structure of the observational signals.

```
        ╭──────╮     ╭──────╮         ← increasing twist
       ╭╯ ~~/~~╰╮  ╭╯ ~~/~~╰╮            = free energy
       │ ~~/~~~~│  │ ~~/~~~~│
       ╰╮~~/~~~╭╯  ╰╮~~/~~~╭╯
        ╰──────╯     ╰──────╯
    - - - - - Instability Threshold - - - - -
    ═══════════════════════════════════════
               Solar Photosphere
             ↑                 ↑
         Footpoint         Footpoint
```

---

## Instability Framework

### Variance-Based Instability Baseline

The rolling variance of the soft X-ray flux 𝑋(𝑡) over a sliding window of length 𝐿 is the core precursor diagnostic:

> Var_𝐿[𝑋](𝑡) = (1/𝐿) Σᵢ₌₀^{𝐿−1} (𝑋(𝑡 − 𝑖) − 𝑋̄_𝐿(𝑡))²

This captures short-timescale fluctuations in radiative output that precede flare onset. A **composite instability indicator** integrates multiple channels:

> 𝐼(𝑡) = 𝑤₁ Var_𝐿[𝑋](𝑡) + 𝑤₂ Var_𝐿[𝐵](𝑡) + 𝑤₃ |d/dt EUV(𝑡)|

where weights 𝑤₁, 𝑤₂, 𝑤₃ are calibrated from historical flare catalogues.

### Triadic Instability Operator

The **triadic instability functional** ΔΦ(𝑡) integrates three complementary signal dimensions:

> ΔΦ(𝑡) = α |Δ𝑆(𝑡)| + β |Δ𝐼(𝑡)| + γ |Δ𝐶(𝑡)|

| Component | Symbol | Physical Meaning |
|-----------|--------|------------------|
| Structural | 𝑆(𝑡) | Coronal magnetic configuration variability (magnetometer proxies, magnetic stress) |
| Informational | 𝐼(𝑡) | Radiative signal complexity (entropy, higher-order X-ray variability) |
| Coherence | 𝐶(𝑡) | Cross-channel coupling between EUV and X-ray flux |

### Regime Classification

ΔΦ(𝑡) maps the solar corona to one of four dynamical states:

| Regime | ΔΦ Range | Physical State |
|--------|----------|----------------|
| 🟢 Isostasis | ΔΦ < 0.15 | Quiet corona, energy balance |
| 🟡 Allostasis | 0.15 ≤ ΔΦ < 0.35 | Progressive magnetic stress accumulation |
| 🟠 High-Allostasis | 0.35 ≤ ΔΦ < 0.40 | Critical instability buildup |
| 🔴 Collapse (Flare) | ΔΦ ≥ 0.40 | Magnetic reconnection, energy release |

```
  C │                              ★ FLARE ONSET
    │                           ╱   ΔΦ ≥ 0.40
    │                        ╱
    │  · · · · · · · · · · ╱ · ·  ← Critical Threshold
    │                    ╭╯  High-Allostasis  (0.35–0.40)
    │                ╭───╯   Allostasis       (0.15–0.35)
    │  ○─────────────╯       Isostasis        (< 0.15)
    └─────────────────────────────────────────── I
          ╲
           S
       [ ΔΦ increases along trajectory → ]
```

### Phase–Memory Embedding

For a deeper dynamical interpretation, the observed signals are embedded into a structured phase–memory coordinate system:

> ψ(𝑡) = 𝑡 + 𝑖 φ(𝑡) + 𝑗 χ(𝑡)

where φ(𝑡) is a phase-coherence coordinate (cross-channel coupling) and χ(𝑡) is a slow memory/hysteresis component encoding accumulated magnetic stress. This non-Markovian framework enables sensitivity to **coherence degradation** and **temporal acceleration** — both early precursors of flare onset that amplitude-only monitoring misses.

---

## Domains

### 🌀 Spiral‑Time (`domains/spiral_time/`)

Implements the phase–memory embedding ψ(𝑡) = 𝑡 + 𝑖φ(𝑡) + 𝑗χ(𝑡) and the triadic instability operator ΔΦ(𝑡). Computes regime classifications and tests the falsification criterion: shuffling the time series should degrade ΔΦ's predictive power, confirming that temporal memory is essential.

**Key signals:** X-ray flux, phase-coherence proxies, memory coordinate χ(𝑡)

### ⚡ Energy Transfer (`domains/energy_transfer/`)

Analyzes how flare energy distributes across wavelengths using X-ray and EUV irradiance datasets. Connects to the composite indicator 𝐼(𝑡) and the EUV derivative term |d/dt EUV(𝑡)|.

**Key signals:** GOES X-ray flux 𝑋(𝑡), EUV irradiance EUV(𝑡)

### 🧲 Topology (`domains/topology/`)

Uses magnetometer data to study magnetic field variations and their relationship to flare onset. Implements the structural variability component 𝑆(𝑡) and the slow memory variable χ(𝑡) approximated via long-window magnetometer statistics.

**Key signals:** GOES magnetometer proxy 𝐵(𝑡), rolling variance Var_𝐿[𝐵](𝑡)

### 💥 Release Events (`domains/release_events/`)

Examines flare initiation, peak flux, decay, and classification using GOES flare event data. Implements the event overlay analysis — comparing rolling variance and ΔΦ against catalogued flare timestamps {𝑡ₖ} to evaluate precursor lead times.

**Key signals:** Flare catalogue {𝑡ₖ} with GOES classes A, B, C, M, X

---

## Data Sources

All observational data is fetched at runtime from the [NOAA Space Weather Prediction Center (SWPC)](https://services.swpc.noaa.gov/json/) via `shared/data_loader.py`.

| File | Observable | Physical Meaning |
|------|------------|------------------|
| `xrays-7-day.json` | 𝑋(𝑡) | Coronal radiative output / flare intensity proxy |
| `xray-flares-7-day.json` | {𝑡ₖ} | Event timestamps and classes (A, B, C, M, X) |
| `xray-background-7-day.json` | 𝑋_bg(𝑡) | Quiet-Sun baseline emission |
| `magnetometers-7-day.json` | 𝐵(𝑡) | Field perturbation surrogate |
| `euvs-7-day.json` | EUV(𝑡) | Coronal heating proxy |

All data covers a **7-day rolling window** at native GOES cadence. The analysis pipeline is designed to generalize directly to multi-month or multi-year archives for full ROC/AUC statistical validation.

See `CITATIONS.md` for full data references.

---

## Repository Structure

```
.                                   # Root of the Solar Flare Detection repository
├── README.md                       # Project overview, structure, usage
├── CHANGELOG.md                    # Version history and release notes
├── CITATIONS.md                    # Scientific references and data sources
├── CONTRIBUTING.md                 # Contribution guidelines
├── LICENSE                         # MIT license for open-source use
├── PAPER.md                        # Companion research paper draft
├── requirements.txt                # Python dependencies
├── .github/                        # GitHub automation and CI configuration
│   └── workflows/                  # Continuous integration pipelines
│       ├── ci.yml                  # Main CI pipeline (lint / import check)
│       ├── python-tests.yml        # Python test suite (3.10 / 3.11 / 3.12)
│       └── julia-tests.yml         # Julia test suite (1.10 / 1 latest stable)
│
├── shared/                         # Shared Python utilities and Julia helpers
│   ├── __init__.py                 # Python package init
│   ├── math_utils.py               # Core mathematical functions
│   ├── data_loader.py              # GOES/EUVS data loading helpers
│   ├── plot_utils.py               # Plotting utilities
│   ├── DataLoader.jl               # Julia data-loading helper
│   └── README.md                   # Shared layer documentation
│
├── domains/                        # Domain logic and educational examples
│   ├── spiral_time/                # ψ(t), ΔΦ(t), regime classification
│   ├── energy_transfer/            # Multi-channel composite indicator I(t)
│   ├── topology/                   # Magnetometer variance, memory variable χ(t)
│   └── release_events/             # Flare event overlays, lead-time analysis
│
├── tools/                          # High-performance Julia modules
│   ├── spiral_time/                # Julia models for spiral-time dynamics
│   ├── energy_transfer/            # Julia models for energy distribution
│   ├── topology/                   # Julia models for magnetic topology
│   └── release_events/             # Julia models for flare event analysis
│
├── test/                           # Automated test suite
│   ├── conftest.py                 # pytest configuration (sys.path setup)
│   ├── test_math_utils.py          # Unit tests for shared/math_utils.py
│   ├── test_data_loader.py         # Smoke tests for shared/data_loader.py
│   ├── test_plot_utils.py          # Smoke tests for shared/plot_utils.py
│   ├── test_integration_pipeline.py # End-to-end pipeline integration test
│   ├── runtests.jl                 # Julia master test runner
│   ├── test_spiral_time.jl         # Julia tests for SpiralTime module
│   ├── test_energy_transfer.jl     # Julia tests for EnergyTransfer module
│   ├── test_topology.jl            # Julia tests for Topology module
│   └── test_release_events.jl      # Julia tests for ReleaseEvents module
│
├── docs/                           # Documentation and educational material
│   ├── overview.md                 # High-level project overview
│   ├── how_to_navigate.md          # Guide to repo structure and workflow
│   ├── glossary.md                 # Definitions of scientific terms
│   └── diagrams/                   # Supporting diagrams and illustrations

```

---

## Python Layer (Educational)

Python is used for loading and visualizing datasets, simple analysis and example workflows, generating plots and diagrams, and teaching domain concepts.

Each domain contains an `examples_python/` folder with scripts and notebooks covering:

- Rolling variance computation Var_𝐿[𝑋](𝑡) from raw GOES X-ray flux
- Composite indicator 𝐼(𝑡) construction and weight calibration
- Flare event overlay plots with lead-time windows
- Regime classification using the ΔΦ threshold table
- Phase–memory coordinate visualization

---

## Julia Layer (Computational)

Julia is used for numerical models, simulation kernels, energy calculations, and topology and flare-event analysis.

Each domain has a matching folder under `tools/` for:

- High-cadence rolling variance and triadic operator ΔΦ computation
- Non-Markovian memory-kernel diagnostics and χ(𝑡) estimation
- Large-scale ROC/AUC evaluation across multi-year GOES archives
- Flare-class stratification (C, M, X) and solar cycle phase analysis
- Spectral sideband structure and multiscale entropy calculations

---

## Getting Started

### Python

```bash
pip install -r requirements.txt
python domains/<domain>/examples_python/example_1.py
```

### Julia

```bash
cd tools/<domain>
julia --project
```

---

## Key Concepts Glossary

| Term | Definition |
|------|------------|
| **Magnetic reconnection** | Process where oppositely directed field lines converge, releasing stored magnetic energy as radiation and particle acceleration |
| **Coronal loop** | Arched magnetic flux tube anchored in the photosphere; primary site of free energy storage |
| **Rolling variance** Var_𝐿[𝑋](𝑡) | Short-window fluctuation measure used as a pre-flare instability proxy |
| **Triadic operator** ΔΦ(𝑡) | Composite functional integrating structural 𝑆, informational 𝐼, and coherence 𝐶 components |
| **Isostasis / Allostasis** | Quiet vs. stressed coronal states defined by ΔΦ thresholds |
| **Non-Markovian dynamics** | System behavior where past history — not just present state — determines future evolution |
| **χ(𝑡)** | Slow memory variable encoding accumulated magnetic stress in active regions |
| **GOES** | Geostationary Operational Environmental Satellite; primary data source for X-ray and magnetometer observations |

Full glossary available in `docs/glossary.md`.

---

## Contributing

Pull requests are welcome. Please follow the domain structure, keep documentation clear, and ensure reproducibility. New domains should include both a Python educational layer and a Julia computational module, with data fetched via `shared/data_loader.py`.

---

## Citations

All scientific references, data sources, and acknowledgments are listed in `CITATIONS.md`.

Primary reference: Krüger, M. & Feeney, D.M. Jr. (2026). *Detection of Solar Plasma Instabilities Using Multi-Channel GOES Observations: Toward Early Solar Flare Forecasting.*

---

## License

This project is licensed under the **MIT License**.

---

## Acknowledgements

The authors gratefully acknowledge the use of AI assistants—specifically Microsoft Copilot and Anthropic Claude—for support in code refinement, documentation editing, and organizational clarity. These tools contributed to improving readability and consistency, while all conceptual development, scientific reasoning, and final implementation decisions were carried out by the authors.

