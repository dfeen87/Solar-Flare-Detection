# Peer-Review Guide — Solar Flare Detection

> **Purpose:** This document is written for academic peer reviewers, collaborators,
> and independent reproducers of the research presented in
> [PAPER.md](PAPER.md) (*"Detection of Solar Plasma Instabilities Using
> Multi-Channel GOES Observations: Toward Early Solar Flare Forecasting"*,
> Krüger & Feeney, 2026).  It maps every paper section and equation to its
> implementing source file, shows how to reproduce every published figure and
> table from scratch, and provides a structured reviewer checklist.

---

## Table of Contents

1. [Repository at a Glance](#1-repository-at-a-glance)
2. [Quick Start for Reviewers](#2-quick-start-for-reviewers)
3. [Document Map](#3-document-map)
4. [Paper-to-Code Mapping](#4-paper-to-code-mapping)
5. [Equation-to-Function Reference](#5-equation-to-function-reference)
6. [Reproducing All Published Figures and Tables](#6-reproducing-all-published-figures-and-tables)
7. [Data Sources and Reproducibility](#7-data-sources-and-reproducibility)
8. [Test Suite Overview](#8-test-suite-overview)
9. [Limitations and Open Items](#9-limitations-and-open-items)
10. [Reviewer Checklist](#10-reviewer-checklist)

---

## 1  Repository at a Glance

| Attribute | Details |
|-----------|---------|
| **Language** | Python 3.10+ (educational layer) · Julia 1.9+ (computational stubs) |
| **Dependencies** | `numpy ≥ 1.24`, `pandas ≥ 2.0`, `matplotlib ≥ 3.7` (see [`requirements.txt`](requirements.txt)) |
| **Data source** | NOAA SWPC public REST API (no registration required) |
| **License** | MIT (see [`LICENSE`](LICENSE)) |
| **CI status** | [![CI](https://github.com/dfeen87/Solar-Flare-Detection/actions/workflows/ci.yml/badge.svg)](https://github.com/dfeen87/Solar-Flare-Detection/actions/workflows/ci.yml) [![Python Tests](https://github.com/dfeen87/Solar-Flare-Detection/actions/workflows/python-tests.yml/badge.svg)](https://github.com/dfeen87/Solar-Flare-Detection/actions/workflows/python-tests.yml) |
| **Authors** | Marcel Krüger (ORCID: 0009-0002-5709-9729) · Don Michael Feeney Jr. (ORCID: 0009-0003-1350-4160) |

### High-level layout

```
Solar-Flare-Detection/
├── PAPER.md                  ← full research paper (read alongside this file)
├── PEER_REVIEW.md            ← this document
├── README.md                 ← project overview and physics background
├── shared/                   ← all equation implementations (Python)
│   ├── math_utils.py         ← Eqs. (3)–(7)
│   ├── data_loader.py        ← NOAA SWPC data retrieval
│   └── plot_utils.py         ← matplotlib helpers (Figures 6–8)
├── domains/                  ← runnable example scripts
│   ├── spiral_time/          ← Eq. (6), (7), regime classification
│   ├── energy_transfer/      ← Eq. (5) composite indicator
│   ├── topology/             ← Var_L[B](t), χ(t)
│   └── release_events/       ← flare event overlay
├── tools/                    ← Julia module stubs (type definitions)
├── test/                     ← pytest suite (Python) + Julia test runner
├── output/paper_figures/     ← committed publication-ready outputs
└── docs/                     ← supplementary documentation
```

---

## 2  Quick Start for Reviewers

### 2.1  Environment setup

```bash
git clone https://github.com/dfeen87/Solar-Flare-Detection.git
cd Solar-Flare-Detection

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
pip install pytest               # only needed to run the test suite
```

### 2.2  One-command verification

The fastest way to verify the complete pipeline works end-to-end — without
requiring internet access — is the integration test:

```bash
pytest test/test_integration_pipeline.py -v
```

This test loads a fully synthetic 7-day dataset, runs every step in the
PAPER.md pipeline (Eqs. 3–7, regime classification), and smoke-tests all plot
helpers.  It finishes in seconds and requires no NOAA API call.

### 2.3  Reproduce the paper figures with live data

```bash
# Figures 6–8 as PNGs (saved to output/paper_figures/)
python domains/spiral_time/examples_python/make_goes_figures.py

# Figures 6–8 + CSV tables A–C + PDF summary report
python domains/spiral_time/examples_python/make_goes_summary_report.py
```

Both scripts fetch the current 7-day GOES feed at runtime; figures will differ
slightly from the committed outputs (which represent a single historical fetch)
but should exhibit the same qualitative features.

---

## 3  Document Map

| Want to understand… | Read… |
|---------------------|-------|
| Scientific motivation & background | [PAPER.md §1–§3](PAPER.md) |
| Observational data channels | [PAPER.md §4](PAPER.md) · [`shared/data_loader.py`](shared/data_loader.py) |
| Core equations (rolling variance, composite indicator, triadic operator, phase–memory embedding) | [PAPER.md §6–§7](PAPER.md) · [Section 5 of this document](#5-equation-to-function-reference) |
| Four dynamical regimes | [PAPER.md §6.4](PAPER.md) · [`shared/math_utils.py` lines 134–169](shared/math_utils.py) |
| Falsification criterion | [PAPER.md §6.5](PAPER.md) |
| Published results (Figures 6–8) | [PAPER.md §9](PAPER.md) · [`output/paper_figures/`](output/paper_figures/) |
| Discussion & limitations | [PAPER.md §10](PAPER.md) · [Section 9 of this document](#9-limitations-and-open-items) |
| Synthetic validation tables | [PAPER.md §Synthetic Validation Tables](PAPER.md) · [`domains/spiral_time/examples_python/synthetic_pipeline_numbers.py`](domains/spiral_time/examples_python/synthetic_pipeline_numbers.py) |
| How to contribute | [`CONTRIBUTING.md`](CONTRIBUTING.md) |
| Scientific terminology | [`docs/glossary.md`](docs/glossary.md) |
| Navigation guide | [`docs/how_to_navigate.md`](docs/how_to_navigate.md) |
| Full references | [`CITATIONS.md`](CITATIONS.md) |

---

## 4  Paper-to-Code Mapping

### §1  Introduction

The introduction motivates using variance growth and multi-channel coherence as
pre-flare precursors.  No standalone code; the theoretical framing is
operationalized by the functions in `shared/math_utils.py`.

### §2–§3  Solar Physics Background · Solar Interior Structure

Descriptive sections.  The magnetic-reconnection ASCII diagram in §2 also
appears in `README.md` lines 31–48.  No code to review.

### §4  Observational Data and Channels

| Paper statement | Implementing code | Location |
|-----------------|-------------------|----------|
| "We use five GOES data products…" | `load_xray_flux()`, `load_xray_flares()`, `load_xray_background()`, `load_magnetometer()`, `load_euvs()` | [`shared/data_loader.py`](shared/data_loader.py) lines 101–245 |
| "Data fetched from NOAA SWPC REST API" | `_load_json()` function + `BASE_URL` constant | [`shared/data_loader.py`](shared/data_loader.py) lines 1–99 |
| "Local cache fallback" | `assets/data/<type>/<file>.json` checked before live fetch | [`shared/data_loader.py`](shared/data_loader.py) lines 57–74 |

### §5  Time-Series Construction

| Paper statement | Implementing code | Location |
|-----------------|-------------------|----------|
| "X(t): soft X-ray flux (0.1–0.8 nm)" | `load_xray_flux()` → column `flux` | [`shared/data_loader.py`](shared/data_loader.py) line 101 |
| "B(t): magnetometer proxy (He component)" | `load_magnetometer()` → column `He` | [`shared/data_loader.py`](shared/data_loader.py) line 188 |
| "EUV(t): EUV irradiance" | `load_euvs()` → column `flux` | [`shared/data_loader.py`](shared/data_loader.py) line 215 |

### §6  Instability Metrics and Triadic Operator Extension

See the detailed [equation-to-function table](#5-equation-to-function-reference)
in Section 5 of this document.

### §7  Operator-Based Non-Equilibrium Interpretation

| Paper statement | Implementing code | Location |
|-----------------|-------------------|----------|
| "ψ(t) = t + iφ(t) + jχ(t) — phase–memory embedding" | `compute_chi()` for χ(t); φ(t) proxy = rolling correlation C(t) | [`shared/math_utils.py`](shared/math_utils.py) lines 252–279 |
| "ψ(t) trajectory plot (φ vs χ)" | `plot_psi_trajectory()` | [`shared/plot_utils.py`](shared/plot_utils.py) |
| Full pipeline using ψ(t) | `full_pipeline_demo.py` | [`domains/spiral_time/examples_python/full_pipeline_demo.py`](domains/spiral_time/examples_python/full_pipeline_demo.py) |

### §9  Results

| Paper figure / table | Script to reproduce | Output path |
|----------------------|---------------------|-------------|
| **Figure 6** — GOES X-ray flux time series | `make_goes_figures.py` or `make_goes_summary_report.py` | `output/paper_figures/fig6_goes_xray_flux.png` |
| **Figure 7** — Rolling variance Var_L[X](t) | same as above | `output/paper_figures/fig7_windowed_variance.png` |
| **Figure 8** — Flare event overlay | same as above | `output/paper_figures/fig8_flare_event_overlay.png` |
| **Table A** — X-ray flux values | `make_goes_summary_report.py` | `output/paper_figures/goes_table_a_flux.csv` |
| **Table B** — Rolling variance values | same as above | `output/paper_figures/goes_table_b_rolling_variance.csv` |
| **Table C** — Flare overlay | same as above | `output/paper_figures/goes_table_c_flare_overlay.csv` |
| **PDF summary report** | same as above | `output/paper_figures/goes_summary_report.pdf` |

### §Synthetic Validation Tables

The synthetic tables S1–S4 in PAPER.md are generated by:

```bash
python domains/spiral_time/examples_python/synthetic_pipeline_numbers.py
```

This script constructs a deterministic 7-day synthetic dataset (no network),
runs the full pipeline, and prints formatted numerical tables matching those in
the paper.

---

## 5  Equation-to-Function Reference

All equations are implemented in [`shared/math_utils.py`](shared/math_utils.py).

### Eq. (3) — Rolling Variance

**Paper definition:**

> Var_L[X](t) = (1/L) Σᵢ₌₀^{L−1} (X(t−i) − X̄_L(t))²

**Implementation:**

```python
# shared/math_utils.py  lines 30–57
def rolling_variance(series: np.ndarray, L: int) -> np.ndarray:
    result = np.full_like(series, np.nan, dtype=float)
    for i in range(L - 1, len(series)):
        window = series[i - L + 1 : i + 1]
        result[i] = np.mean((window - np.mean(window)) ** 2)
    return result
```

**Test coverage:** `test/test_math_utils.py` — `TestRollingVariance` class.

**Used in:** `energy_transfer/composite_indicator_demo.py`, `topology/magnetometer_variance_demo.py`, `spiral_time/full_pipeline_demo.py`.

---

### Eq. (4) — Rolling Mean (auxiliary)

**Paper definition:**

> X̄_L(t) = (1/L) Σᵢ₌₀^{L−1} X(t−i)

Computed inline via `np.mean(window)` inside `rolling_variance()` (source file
`shared/math_utils.py`, line 56 — the innermost expression of the loop body).
Not a separate function.

---

### Eq. (5) — Composite Instability Indicator

**Paper definition:**

> I(t) = w₁ Var_L[X](t) + w₂ Var_L[B](t) + w₃ |d/dt EUV(t)|

**Implementation:**

```python
# shared/math_utils.py  lines 214–249
def compute_composite_indicator(
    var_x_norm, var_b_norm, d_euv_norm,
    w1=1/3, w2=1/3, w3=1/3,
) -> np.ndarray:
    return w1 * var_x_norm + w2 * var_b_norm + w3 * d_euv_norm
```

The `|d/dt EUV(t)|` term is computed separately by:

```python
# shared/math_utils.py  lines 81–98
def euv_derivative(euv: np.ndarray) -> np.ndarray:
    return np.abs(np.gradient(euv))
```

All three components are individually normalized to [0, 1] via `normalize_01()`
(lines 60–78) before combining, ensuring equal-weight comparability.

**Test coverage:** `test/test_math_utils.py` — `TestCompositeIndicator` class.

**Used in:** `energy_transfer/composite_indicator_demo.py`, `spiral_time/full_pipeline_demo.py`.

---

### Eq. (6) — Triadic Instability Operator

**Paper definition:**

> ΔΦ(t) = α |ΔS(t)| + β |ΔI(t)| + γ |ΔC(t)|

**Implementation:**

```python
# shared/math_utils.py  lines 172–211
def compute_delta_phi(
    S, I, C,
    alpha=1/3, beta=1/3, gamma=1/3,
) -> np.ndarray:
    dS = np.abs(np.diff(S, prepend=np.nan))
    dI = np.abs(np.diff(I, prepend=np.nan))
    dC = np.abs(np.diff(C, prepend=np.nan))
    return alpha * dS + beta * dI + gamma * dC
```

Default weights α = β = γ = 1/3 (equal contribution). The first element of the
returned array is always `NaN` because first-differencing requires a prior
value.

**Component mapping:**

| Triadic component | Variable | Physical proxy |
|-------------------|----------|----------------|
| Structural S(t) | `rolling_variance(B, L)` | GOES magnetometer He field |
| Informational I(t) | `rolling_variance(X, L)` | GOES X-ray flux variance |
| Coherence C(t) | `rolling_correlation(X, EUV, L)` | X-ray / EUV Pearson correlation |

**Test coverage:** `test/test_math_utils.py` — `TestComputeDeltaPhi` class.

**Used in:** `spiral_time/variance_and_regime_demo.py`, `spiral_time/full_pipeline_demo.py`.

---

### Eq. (7) — Phase–Memory Embedding

**Paper definition:**

> ψ(t) = t + iφ(t) + jχ(t)

**Implementation notes:**

- χ(t) (slow memory coordinate): `compute_chi()` at lines 252–279.
- φ(t) (phase-coherence coordinate): operationalized as the rolling Pearson
  correlation C(t) between X-ray flux and EUV (`rolling_correlation()` at lines 101–131).
- The full ψ(t) trajectory is not a single function call; it is assembled in
  `full_pipeline_demo.py` and rendered by `plot_psi_trajectory()` in `plot_utils.py`.

**Memory variable χ(t):**

```python
# shared/math_utils.py  lines 252–279
def compute_chi(var_b: np.ndarray, window_L: int) -> np.ndarray:
    # χ(t) ≈ ∫₀ᵗ Var_L[B](τ) dτ  (cumulative sum as trapezoidal approx.)
    integrand = np.where(np.isnan(var_b), 0.0, var_b)
    chi = np.cumsum(integrand)
    chi[: window_L - 1] = np.nan
    return chi
```

**Test coverage:** `test/test_math_utils.py` — `TestComputeChi` class.

---

### Regime Classification — §6.4

```python
# shared/math_utils.py  lines 134–169
REGIME_BOUNDS  = [0.15, 0.35, 0.40]
REGIME_LABELS  = ["Isostasis", "Allostasis", "High-Allostasis", "Collapse"]
REGIME_COLORS  = ["#2ecc71", "#f1c40f", "#e67e22", "#e74c3c"]

def classify_regime(delta_phi_norm: float) -> str:
    if delta_phi_norm < 0.15:  return "Isostasis"
    if delta_phi_norm < 0.35:  return "Allostasis"
    if delta_phi_norm < 0.40:  return "High-Allostasis"
    return "Collapse"
```

**Test coverage:** `test/test_math_utils.py` — `TestClassifyRegime` class.

---

## 6  Reproducing All Published Figures and Tables

All committed outputs live in `output/paper_figures/`.  Each can be regenerated
from scratch with the commands below (requires internet access to NOAA SWPC):

### Figure 6 — GOES X-ray flux time series (§9.1)

```bash
python domains/spiral_time/examples_python/make_goes_figures.py
# → output/paper_figures/fig6_goes_xray_flux.png
```

Renders a semi-logarithmic X-ray flux plot annotated with flare-class color
bands (X=red, M=orange, C=yellow, B/A=gray) using `plot_xray_flux()` in
`shared/plot_utils.py`.

### Figure 7 — Rolling variance Var_L[X](t) (§9.2)

```bash
python domains/spiral_time/examples_python/make_goes_figures.py
# → output/paper_figures/fig7_windowed_variance.png
```

Plots the rolling variance with window length L = 200 data points, produced by
`rolling_variance()` (Eq. 3) and rendered by `plot_rolling_variance()` in
`shared/plot_utils.py`.

### Figure 8 — Flare event overlay (§9.3)

```bash
python domains/spiral_time/examples_python/make_goes_figures.py
# → output/paper_figures/fig8_flare_event_overlay.png
```

Overlays GOES flare catalogue timestamps onto the X-ray flux time series using
`plot_flare_overlay()` in `shared/plot_utils.py`.

### CSV Tables A, B, C and PDF report

```bash
python domains/spiral_time/examples_python/make_goes_summary_report.py
# → output/paper_figures/goes_table_a_flux.csv
# → output/paper_figures/goes_table_b_rolling_variance.csv
# → output/paper_figures/goes_table_c_flare_overlay.csv
# → output/paper_figures/goes_summary_report.pdf
```

### Synthetic validation tables S1–S4 (PAPER.md appendix)

```bash
python domains/spiral_time/examples_python/synthetic_pipeline_numbers.py
```

Runs the full pipeline on a deterministic synthetic dataset (no internet
required) and prints Tables S1–S4 to stdout.  Output figures are saved to
`output/synthetic_pipeline/`.

### All domain examples in one sequence

```bash
python domains/spiral_time/examples_python/full_pipeline_demo.py
python domains/spiral_time/examples_python/variance_and_regime_demo.py
python domains/energy_transfer/examples_python/composite_indicator_demo.py
python domains/topology/examples_python/magnetometer_variance_demo.py
python domains/release_events/examples_python/flare_overlay_demo.py
```

---

## 7  Data Sources and Reproducibility

### NOAA SWPC REST API

All observational data are fetched at runtime from NOAA's public API:

| Dataset | Endpoint | DataFrame column(s) |
|---------|----------|---------------------|
| X-ray flux | `https://services.swpc.noaa.gov/json/goes/primary/xrays-7-day.json` | `time_tag`, `flux` |
| Flare catalogue | `.../xray-flares-7-day.json` | `begin_time`, `max_time`, `class` |
| X-ray background | `.../xray-background-7-day.json` | `time_tag`, `current_class` |
| Magnetometer | `.../magnetometers-7-day.json` | `time_tag`, `He`, `Hn`, `Hc` |
| EUV irradiance | `.../euvs-7-day.json` | `time_tag`, `flux` |

The API delivers a rolling 7-day window; data change with every fetch.

### Local cache

Place any previously downloaded `.json` file under
`assets/data/<type>/<filename>.json` to bypass the live fetch.  The loader
checks for local files first (`shared/data_loader.py` lines 57–74).  This
enables fully offline reproduction using archived snapshots.

### Committed outputs

The files in `output/paper_figures/` were generated during a specific fetch
on the date recorded inside each CSV (`time_utc` column).  They are committed
for reviewers who wish to inspect outputs without running any code.

---

## 8  Test Suite Overview

### Python tests

Run all tests:

```bash
pytest test/ -v
```

| Test file | What it covers |
|-----------|----------------|
| `test/test_math_utils.py` | Unit tests for every function in `shared/math_utils.py` — correctness of `rolling_variance`, `normalize_01`, `euv_derivative`, `rolling_correlation`, `classify_regime`, `compute_delta_phi`, `compute_composite_indicator`, `compute_chi` |
| `test/test_data_loader.py` | Smoke tests for `shared/data_loader.py`; tests that skip automatically when offline |
| `test/test_plot_utils.py` | Smoke tests for all `shared/plot_utils.py` helpers (non-interactive matplotlib backend) |
| `test/test_integration_pipeline.py` | **End-to-end pipeline** — synthetic data → all metrics → regime classification → all plot types.  No network access required. |
| `test/test_make_goes_scripts.py` | Tests for figure-generation scripts |

### Julia tests

```bash
cd test
julia runtests.jl
```

Julia test files cover the type-stub modules in `tools/`:
`test_spiral_time.jl`, `test_energy_transfer.jl`, `test_topology.jl`,
`test_release_events.jl`.

### CI pipelines

| Workflow | Trigger | Scope |
|----------|---------|-------|
| `.github/workflows/ci.yml` | Every push/PR | Lint + import check |
| `.github/workflows/python-tests.yml` | Every push/PR | Python 3.10/3.11/3.12 test matrix |
| `.github/workflows/julia-tests.yml` | Every push/PR | Julia 1.10 + latest stable |

---

## 9  Limitations and Open Items

The following limitations are acknowledged in [PAPER.md §10](PAPER.md) and are
documented here for reviewers:

| Limitation | Status | Location in paper |
|------------|--------|-------------------|
| **No ROC/AUC statistics** — the current 7-day window is too short to compute reliable false-alarm rates or receiver-operating-characteristic curves | Known; stated as future work | §10.3 |
| **Weight calibration** — coefficients α, β, γ (Eq. 6) and w₁, w₂, w₃ (Eq. 5) default to equal 1/3; calibration against multi-year flare catalogues is deferred | Known | §6.1, §6.2 |
| **Magnetometer proxy** — the GOES magnetometer is not a direct photospheric field measurement; it serves as a coronal environment proxy only | Acknowledged | §4.1 |
| **Julia modules are stubs** — `tools/*/` contain type definitions and documented function signatures but implementations raise `error("Not yet implemented")` | Known; stubs are typed and tested | `docs/how_to_navigate.md` |
| **No multi-year validation** — the framework is demonstrated on a 7-day window; statistical validation against historical flare catalogues (e.g. NOAA GOES archive 2010–2024) is future work | Known | §10.3 |
| **Falsification test (§6.5) not yet run** — the time-shuffling experiment is described theoretically but not executed in the current codebase | Planned | §6.5 |

---

## 10  Reviewer Checklist

Use this checklist to verify the scientific and technical claims made in the
companion paper [PAPER.md](PAPER.md).

### Scientific claims

- [ ] **Eq. (3) rolling variance** is correctly implemented — compare paper
  definition with `rolling_variance()` in `shared/math_utils.py` lines 30–57.
- [ ] **Eq. (5) composite indicator** weights are configurable and default to
  equal weighting — see `compute_composite_indicator()` lines 214–249.
- [ ] **Eq. (6) triadic operator** uses first differences of S, I, C — see
  `compute_delta_phi()` lines 172–211.
- [ ] **Eq. (7) memory variable χ(t)** is computed as a cumulative sum of
  `Var_L[B](t)` — see `compute_chi()` lines 252–279.
- [ ] **Regime thresholds** (0.15, 0.35, 0.40) match Table 2 of PAPER.md §6.4
  and `REGIME_BOUNDS` in `shared/math_utils.py` (defined on the first non-comment
  constant line after the module docstring, currently line 21).

### Reproducibility

- [ ] `pytest test/test_integration_pipeline.py -v` passes with no network
  access required.
- [ ] `pytest test/test_math_utils.py -v` passes (all unit tests green).
- [ ] `python domains/spiral_time/examples_python/make_goes_figures.py`
  produces Figures 6–8 matching the qualitative description in §9.
- [ ] `python domains/spiral_time/examples_python/synthetic_pipeline_numbers.py`
  prints tables consistent with Tables S1–S4 in the paper appendix.

### Data and transparency

- [ ] NOAA SWPC API endpoints are publicly accessible without authentication
  (verify `shared/data_loader.py` `BASE_URL`).
- [ ] Committed CSV tables in `output/paper_figures/` contain timestamps and
  numeric values consistent with the paper's description.
- [ ] No private or proprietary data are used; all data are fetchable from the
  public NOAA SWPC JSON feeds.

### Code quality

- [ ] All equation-implementing functions have docstrings cross-referencing the
  paper equation number.
- [ ] `shared/math_utils.py` module constants (`REGIME_BOUNDS`, `REGIME_LABELS`,
  `REGIME_COLORS`) match the paper's threshold table.
- [ ] The CI badges at the top of `README.md` are green (all automated tests pass).

### Acknowledged limitations

- [ ] Reviewer has read §10 (Discussion) and is satisfied that ROC/AUC
  deferral, weight calibration, and Julia stub status are adequately disclosed.
- [ ] The 7-day data window limitation (no multi-year validation) is understood.

---

*For questions or to report discrepancies, open an issue at
<https://github.com/dfeen87/Solar-Flare-Detection/issues> or contact the
corresponding author at marcelkrueger092@gmail.com.*
