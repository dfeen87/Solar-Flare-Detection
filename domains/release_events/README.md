# 💥 Release Events Domain

## Purpose

The `release_events` domain examines **solar flare initiation and event
cataloguing** using the GOES flare event data. It implements the event overlay
analysis from PAPER.md §9.3 (Figures 6–8), comparing rolling variance against
catalogued flare timestamps to evaluate **precursor lead times**.

## Key Constructs

### Flare Event Catalogue

GOES catalogues each flare event with:

| Field | Description |
|-------|-------------|
| time_begin | Flare start time |
| time_max   | Peak flux time |
| time_end   | Flare end time |
| class_type | GOES class letter (A, B, C, M, X) |
| class_num  | Numeric qualifier (e.g. 2.3 for M2.3) |

### Event Overlay Analysis — PAPER.md §9.3

Vertical lines at each flare time tₖ are overlaid on X-ray flux and rolling
variance plots. Colour coding:

| Class | Color |
|-------|-------|
| X | 🔴 Red |
| M | 🟠 Orange |
| C | 🟡 Yellow |
| B/A | ⚪ Gray |

This allows visual assessment of how well Var_L[X](t) rises **before** flare
onset — the lead-time diagnostic for early warning systems.

## Running the Example

```bash
# From the repo root:
pip install -r requirements.txt
python domains/release_events/examples_python/flare_overlay_demo.py
```

Output figure is saved to `examples_python/output/flare_overlay_demo.png`.

## Julia Module

High-performance stubs live in `tools/release_events/ReleaseEvents.jl`.
