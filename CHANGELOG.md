# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
