# How to Navigate the Solarflare Repository

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
│   └── data_loader.py              # Loads all 5 GOES data files (local + NOAA fallback)
│
├── domains/                        # Domain logic and educational Python examples
│   ├── spiral_time/                # ψ(t), ΔΦ(t), regime classification
│   │   ├── README.md
│   │   └── examples_python/
│   │       └── variance_and_regime_demo.py
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
├── docs/                           # Documentation
│   ├── overview.md                 # Project overview (this area)
│   ├── how_to_navigate.md          # This file
│   └── glossary.md                 # Scientific glossary
│
└── assets/
    └── data/                       # GOES data (fetched from NOAA at runtime)
        ├── xray/
        ├── magnetometers/
        └── euvs/
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
assets/data/                                     (rolling variance,
(local cache)                                     ΔΦ, I(t), χ(t), events)
```

---

## Adding a New Domain

1. Create `domains/<name>/README.md` explaining the domain.
2. Add Python example(s) in `domains/<name>/examples_python/`.
3. Create `tools/<name>/<Name>.jl` with Julia stubs and `Project.toml`.
4. Update `docs/overview.md` to describe the new domain.
