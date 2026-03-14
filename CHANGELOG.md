# Changelog

## **2.2.0 — NOAA Catalogue Forecasting Release** — 2026-03-14
**Added**
- NOAA flare catalogue ingestion (`load_noaa_flare_catalogue`)
- Flare–ΔΦ alignment helper (`align_flare_onsets`)
- Precursor‑window evaluation engine (`evaluate_precursor_window`)
- Full end‑to‑end experiment script (`eval_flare_catalogue.py`)
- ROC/AUC computation, lead‑time analysis, and ΔΦ(t) visualizations
- Section 12 of `ANALYSIS_AND_VALIDATION.md` populated with real forecasting results

**Results**
- AUC = 0.7875 over 67 January 2024 flares  
- Median lead time ≈ 11.34 hours  
- Balanced threshold θ ≈ 0.19 (TPR 0.88, FPR 0.14)

**Quality**
- 0 CodeQL alerts  
- All 229 tests passing  

---

## **2.1.0 — ΔΦ(t) Operator Stabilization** — 2026-03-13
**Added**
- Log‑normalized ΔΦ(t) computation for XRS data  
- Improved backward‑difference operator  
- Consistent timestamp normalization across ingestion modules  

**Changed**
- Unified naming conventions for ΔΦ‑related columns  
- Improved error handling in data loaders  

**Fixed**
- Minor inconsistencies in XRS flux parsing  
- Edge‑case timestamp alignment issues  

---

## **2.0.0 — Major Architecture Consolidation** — 2026-03-13
**Added**
- Full modularization of shared utilities (`shared/`)  
- New analysis modules under `analysis/`  
- Experiment harness structure under `experiments/`  
- Initial ΔΦ(t) computation pipeline  

**Changed**
- Restructured repository into stable, documented architecture  
- Standardized data‑loading interfaces  
- Introduced versioned scientific documentation (`ANALYSIS_AND_VALIDATION.md`)  

**Removed**
- Legacy prototype scripts  
- Deprecated preprocessing utilities  

---

## [1.4.0] — 2026-03-08

### Added
- Committed all 7 publication-ready output files to the repository under
  `output/paper_figures/`:
  - `fig6_goes_xray_flux.png` — Fig 6: semilog GOES X-ray flux time series
  - `fig7_windowed_variance.png` — Fig 7: rolling variance (L=200)
  - `fig8_flare_event_overlay.png` — Fig 8: flux with flare-onset markers
  - `goes_table_a_flux.csv` — Table A: time_utc | xray_flux
  - `goes_table_b_rolling_variance.csv` — Table B: time_utc | rolling_variance | window_L
  - `goes_table_c_flare_overlay.csv` — Table C: time_utc | xray_flux | flare_flag | flare_class
  - `goes_summary_report.pdf` — PDF report: title page + Fig 6–8 pages with tables

### Changed
- Updated `.gitignore` to track all files inside `output/paper_figures/`
  (`!output/paper_figures/**`) while keeping `output/synthetic_pipeline/`
  gitignored as before.
- Updated README to reflect that `output/paper_figures/` outputs are now
  committed to version control.

---

## [1.3.0] — 2026-03-08

### Added
- New script: `domains/spiral_time/examples_python/make_goes_summary_report.py`  
  A self-contained reporting tool that:
  - loads real GOES 7‑day flux and flare data via `shared/data_loader.load_xray_flux` and `load_xray_flares`
  - computes `rolling_variance(flux, L=200)` once via `shared/math_utils`
  - produces three numeric CSV tables:
    - `goes_table_a_flux.csv` — `time_utc, xray_flux`
    - `goes_table_b_rolling_variance.csv` — `time_utc, rolling_variance, window_L`
    - `goes_table_c_flare_overlay.csv` — `time_utc, xray_flux, flare_flag, flare_class`
  - regenerates Figures 6–8 at 300 dpi using the existing plotting conventions
  - assembles a multi-page PDF report (`goes_summary_report.pdf`) containing:
    - a title page with GOES data source, observation window, and window length `L`
    - one page per figure embedding the PNG and a sampled table (up to 30 rows, every N‑th row for large datasets)

### Changed
- Improved flare matching logic in Table C:  
  Flux timestamps and flare onset times are rounded to the nearest minute before lookup, ensuring consistent alignment even when `begin_time` falls back to `time_max`.
- Added `_is_valid_time()` helper to handle `NaT` correctly.  
  Pandas converts missing datetimes to `NaT`, and `NaT is not None` evaluates `True`, which previously allowed invalid timestamps to reach `ax.axvline()`.  
  All timestamp validation now uses `pd.isna()`.

### Documentation
- Updated README repository tree:
  - added `make_goes_summary_report.py`
  - added all new `output/paper_figures/` artifacts
- Expanded the Spiral-Time domain section with a reference table covering all five scripts
- Updated *Getting Started* to include the run command for the new reporting script

---

## [1.2.0] — 2026-03-08

### Added
- New publication-ready figure script:  
  `domains/spiral_time/examples_python/make_goes_figures.py`  
  Generates three 300 dpi PNGs in `output/paper_figures/`:
  - `fig6_goes_xray_flux.png` — semilog GOES 0.1–0.8 nm X-ray flux with UTC timestamps.
  - `fig7_windowed_variance.png` — rolling variance using `shared/math_utils.rolling_variance` with `L = 200`.
  - `fig8_flare_event_overlay.png` — flux plot with vertical flare-onset markers from the NOAA catalogue (`begin_time`, fallback to `max_time`).
- Script is fully reproducible and uses only the existing loader functions (`load_xray_flux`, `load_xray_flares`).  
  No new dependencies introduced.

### Changed
- Updated top-level README to synchronize the repository structure with the actual codebase:
  - Expanded all `domains/*/examples_python/` entries with one-line descriptions for each script.
  - Expanded all `tools/*/` entries to include `.jl` source files and `Project.toml`.
  - Added missing `output/` directory tree (`paper_figures/`, `synthetic_pipeline/`).
  - Added missing `CODE_OF_CONDUCT.md` entry and corrected `SECURITY.md` description.
  - Enriched `shared/` and `test/` annotations (exported symbols, offline-skip behavior).
  - Updated *Getting Started → Python* to list all six runnable script paths instead of placeholder examples.

---

## [1.1.0] - 2026-03-08

### Added

- **PR #7 — Shared Julia math utilities, end-to-end pipeline, and Julia tests**
  - `shared/MathUtils.jl` — new Julia module with `normalize_01` and
    `rolling_correlation`, mirroring the pipeline-relevant parts of
    `shared/math_utils.py`. Both functions include docstrings referencing
    PAPER.md sections.
  - `tools/run_pipeline.jl` — end-to-end Julia pipeline script wiring all five
    Julia modules (`DataLoader`, `EnergyTransfer`, `Topology`, `SpiralTime`,
    `ReleaseEvents`) together. Covers data loading, rolling variances, composite
    indicator I(t), ΔΦ(t) regime classification, phase–memory embedding ψ(t),
    and lead-time analysis. Runnable with `julia tools/run_pipeline.jl`.
  - `test/test_math_utils.jl` — Julia unit tests for `MathUtils` covering
    `normalize_01` (basic normalization, constant input, all-NaN, mixed NaN)
    and `rolling_correlation` (perfect positive/negative correlation, constant
    signals, window larger than data, output length).
  - Updated `test/runtests.jl` to include `test_math_utils.jl`.

### Changed

- `shared/README.md` — removed inaccurate "function stubs" / "deferred to a
  future PR" language from the `DataLoader.jl` section; replaced with an
  accurate description of the fully implemented module including a function
  table. Added a new `MathUtils.jl` section with a function table and import
  example.

---

## [1.0.0] - 2026-03-08

### Added

- **PR #1 — Repository skeleton**
  - Top-level project structure: `shared/`, `domains/`, `tools/`, `docs/`,
    `assets/`, `test/`.
  - Shared data loader (`shared/data_loader.py`) with local cache and live
    NOAA SWPC fallback for all five GOES data products.
  - Domain educational examples (`domains/*/examples_python/`) for all four
    domains: spiral time, energy transfer, topology, and release events.
  - Julia module stubs (`tools/*/`) with type definitions and documented
    function signatures for each domain.
  - Initial documentation: `docs/overview.md`, `docs/how_to_navigate.md`,
    `docs/glossary.md`.

- **PR #2 — Julia kernels and shared Python math library**
  - Full Julia computational kernels for all four domains
    (`tools/spiral_time/SpiralTime.jl`, `tools/energy_transfer/EnergyTransfer.jl`,
    `tools/topology/Topology.jl`, `tools/release_events/ReleaseEvents.jl`).
  - Shared Python math library (`shared/math_utils.py`) with `rolling_variance`,
    phase-memory helpers, and regime classification logic.
  - `shared/DataLoader.jl` for GOES data access from Julia.
  - Julia unit test suite (`test/test_spiral_time.jl`, `test/test_topology.jl`,
    `test/test_energy_transfer.jl`, `test/test_release_events.jl`,
    `test/runtests.jl`).

- **PR #3 — `compute_delta_phi` / `compute_composite_indicator` and Python tests**
  - `compute_delta_phi` and `compute_composite_indicator` added to
    `shared/math_utils.py`, implementing Equations 5–6 from PAPER.md.
  - Full Python pytest suite (`test/test_math_utils.py`, `test/test_data_loader.py`,
    `test/conftest.py`) covering shared utilities.

- **PR #4 — Shared visualization utilities, smoke tests, and navigation guide**
  - Shared plot helpers (`shared/plot_utils.py`) for Figures 6–8 from PAPER.md.
  - Smoke tests for visualization (`test/test_plot_utils.py`).
  - `shared/README.md` documenting all shared modules.
  - Navigation guide (`docs/how_to_navigate.md`) with folder-structure diagram
    and "Adding a New Domain" instructions.

- **PR #5 — ΔΦ/ψ/I(t) plot helpers and end-to-end integration test**
  - Additional plot helpers for ΔΦ, ψ(t), and I(t) time series in
    `shared/plot_utils.py`.
  - End-to-end integration test (`test/test_integration_pipeline.py`) exercising
    the complete scientific pipeline with no network dependency.
  - Unified pipeline demo (`domains/spiral_time/examples_python/full_pipeline_demo.py`).

- **PR #6 — Synthetic validation pipeline and PAPER.md demonstration tables**
  - Synthetic validation pipeline (`output/synthetic_pipeline/`) that
    generates reproducible demonstration data matching the tables in PAPER.md.
  - `PAPER.md` with full scientific paper text and demonstration tables
    (Krüger & Feeney, 2026).
  - `CITATIONS.md` with scientific references and data sources.
