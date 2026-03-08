# How to Navigate the Solar Flare Detection Repository

## Folder Structure

```
.
├── README.md                       # Project overview and physics background
├── PAPER.md                        # Full scientific paper (Krüger & Feeney 2026)
├── CITATIONS.md                    # Scientific references and data sources
├── requirements.txt                # Python dependencies (numpy, matplotlib, pandas)
│
├── shared/                         # Shared Python utilities
│   ├── __init__.py
│   ├── README.md                   # Documentation for shared modules
│   ├── data_loader.py              # Loads all 5 GOES data files (local + NOAA fallback)
│   ├── math_utils.py               # Core math functions (rolling_variance, ΔΦ, χ, …)
│   └── plot_utils.py               # Shared visualization helpers (Figures 6–8)
│
├── domains/                        # Domain logic and educational Python examples
│   ├── spiral_time/                # ψ(t), ΔΦ(t), regime classification
│   │   ├── README.md
│   │   └── examples_python/
│   │       ├── variance_and_regime_demo.py
│   │       └── full_pipeline_demo.py   # ← recommended entry point
│   ├── energy_transfer/            # Composite indicator I(t)
│   │   ├── README.md
│   │   └── examples_python/
│   │       └── composite_indicator_demo.py
│   ├── topology/                   # Var_L[B], χ(t)
│   │   ├── README.md
│   │   └── examples_python/
│   │       └── magnetometer_variance_demo.py
│   └── release_events/             # Flare event overlay, lead-time analysis
│       ├── README.md
│       └── examples_python/
│           └── flare_overlay_demo.py
│
├── tools/                          # Julia module stubs (high-performance layer)
│   ├── spiral_time/SpiralTime.jl
│   ├── energy_transfer/EnergyTransfer.jl
│   ├── topology/Topology.jl
│   └── release_events/ReleaseEvents.jl
│
├── test/                           # Python test suite
│   ├── conftest.py                 # pytest configuration (sys.path setup)
│   ├── test_math_utils.py          # Unit tests for shared/math_utils.py (43 tests)
│   ├── test_data_loader.py         # Unit tests for shared/data_loader.py (13 tests)
│   ├── test_plot_utils.py          # Smoke tests for shared/plot_utils.py
│   ├── test_integration_pipeline.py # End-to-end pipeline integration test
│   ├── runtests.jl                 # Julia test runner
│   ├── test_spiral_time.jl
│   ├── test_topology.jl
│   ├── test_energy_transfer.jl
│   └── test_release_events.jl
│
├── docs/                           # Documentation
│   ├── overview.md                 # Project overview (this area)
│   ├── how_to_navigate.md          # This file
│   └── glossary.md                 # Scientific glossary
```

---

## Python vs Julia Split

| Layer | Location | Purpose |
|-------|----------|---------|
| **Python** | `domains/*/examples_python/` | Educational examples, visualization, analysis |
| **Julia**  | `tools/*/` | High-performance numerical modules (stubs in v0.1) |

The Python layer is self-contained and runs immediately with `pip install -r
requirements.txt`. The Julia layer is organized as independent Julia projects
(each folder has a `Project.toml`).

---

## Recommended Entry Point

For a complete, all-in-one demonstration of the full PAPER.md analysis workflow
(raw data → metrics → regime classification → visualization), run:

```bash
python domains/spiral_time/examples_python/full_pipeline_demo.py
```

This script loads all five GOES data products, computes Var_L[X], Var_L[B],
|d/dt EUV|, I(t), C(t), ΔΦ(t), χ(t), and ψ(t), classifies the current solar
activity regime, and saves a four-panel summary figure to
`domains/spiral_time/examples_python/output/full_pipeline_demo.png`.

---

## Running Python Examples

```bash
# Install dependencies (from repo root)
pip install -r requirements.txt

# Run any example
python domains/spiral_time/examples_python/variance_and_regime_demo.py
python domains/energy_transfer/examples_python/composite_indicator_demo.py
python domains/topology/examples_python/magnetometer_variance_demo.py
python domains/release_events/examples_python/flare_overlay_demo.py
```

On first run the scripts call `shared/data_loader.py`, which fetches the live
GOES JSON feeds from NOAA SWPC if the local cache files are absent. Output
figures are written to each domain's `examples_python/output/` directory.

---

## Running Julia Stubs

```bash
cd tools/spiral_time
julia --project
```

The Julia modules currently contain type definitions and documented function
stubs (`error("Not yet implemented")`). Full implementations are deferred to a
future PR.

---

## Data Flow

```
NOAA SWPC API  ──→  shared/data_loader.py  ──→  domain Python scripts  ──→  output figures
                                                 (rolling variance,
                                                  ΔΦ, I(t), χ(t), events)
```

---

## Adding a New Domain

1. Create `domains/<name>/README.md` explaining the domain.
2. Add Python example(s) in `domains/<name>/examples_python/`.
3. Create `tools/<name>/<Name>.jl` with Julia stubs and `Project.toml`.
4. Update `docs/overview.md` to describe the new domain.

---

## Running Python Tests

The `test/` directory contains a pytest suite that covers the shared utilities.

```bash
# Install dependencies (from repo root)
pip install -r requirements.txt
pip install pytest

# Run all Python tests
pytest test/

# Run individual test modules
pytest test/test_math_utils.py -v
pytest test/test_data_loader.py -v
pytest test/test_plot_utils.py -v

# Run the full end-to-end integration test (no network required)
pytest test/test_integration_pipeline.py -v
```

`test/conftest.py` adds the repository root to `sys.path` automatically so
that `shared.*` imports work regardless of the working directory.

The integration test (`test/test_integration_pipeline.py`) exercises the
complete scientific pipeline — loading synthetic data, computing all metrics,
classifying the regime, and smoke-testing the new plot helpers — with no
network dependency.
