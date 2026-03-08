# `shared/` — Shared Python Modules

This directory contains the shared Python utilities used by every domain demo and test in the Solar Flare Detection framework.  These modules implement the mathematical core of PAPER.md and provide common visualization helpers so that the domain-specific scripts remain concise and consistent.

---

## Modules

### `data_loader.py`

Loads the five GOES data products from the NOAA SWPC JSON feeds. A local file cache is also supported: if the JSON files are present at `assets/data/`, they will be used instead of the network request.

| Function | Returns | GOES product |
|---|---|---|
| `load_xray_flux()` | `DataFrame[time, flux]` | X-ray irradiance (1-min) |
| `load_xray_flares()` | `DataFrame[time_begin, time_max, time_end, class_type, class_num]` | Flare event catalogue |
| `load_magnetometer()` | `DataFrame[time, He]` | He-component magnetometer |
| `load_euvs()` | `DataFrame[time, ...]` | EUV irradiance |
| `load_xray_background()` | `DataFrame[time, background_flux]` | X-ray background |

**Import example**

```python
from shared.data_loader import load_xray_flux, load_xray_flares
df_x = load_xray_flux()
df_f = load_xray_flares()
```

---

### `math_utils.py`

Core mathematical functions implementing the PAPER.md equations.  All functions accept and return NumPy arrays.

| Function | PAPER.md Reference | Description |
|---|---|---|
| `rolling_variance(series, L)` | Eq. (3) | Windowed variance Var_L[X](t) |
| `normalize_01(arr)` | — | Min-max normalization to [0, 1] |
| `euv_derivative(euv)` | Eq. (5) — third term | \|d/dt EUV(t)\| via `np.gradient` |
| `rolling_correlation(x, y, L)` | §6.2 | Rolling Pearson correlation C(t) |
| `classify_regime(delta_phi_norm)` | §6.4 | Map ΔΦ → regime label string |
| `compute_delta_phi(S, I, C, ...)` | Eq. (6) | Triadic instability operator ΔΦ(t) |
| `compute_composite_indicator(...)` | Eq. (5) | Composite indicator I(t) |
| `compute_chi(var_b, window_L)` | §6.3 | Memory variable χ(t) |

**Module constants**

| Constant | Value | Meaning |
|---|---|---|
| `REGIME_BOUNDS` | `[0.15, 0.35, 0.40]` | Normalized ΔΦ thresholds (§6.4) |
| `REGIME_LABELS` | `["Isostasis", "Allostasis", "High-Allostasis", "Collapse"]` | Regime names |
| `REGIME_COLORS` | `["#2ecc71", "#f1c40f", "#e67e22", "#e74c3c"]` | Matplotlib hex colors |

**Import example**

```python
from shared.math_utils import rolling_variance, compute_delta_phi, classify_regime
var_x = rolling_variance(flux, L=30)
delta_phi = compute_delta_phi(var_b, var_x, rolling_corr, alpha=1/3, beta=1/3, gamma=1/3)
regime = classify_regime(float(delta_phi_norm[-1]))
```

---

### `plot_utils.py`

Reusable matplotlib plotting helpers that implement the visualization patterns defined in PAPER.md §9 (Figures 6–8) and §6.4.  All functions accept pre-computed NumPy arrays, return `(fig, ax)` tuples for composability, and apply consistent Solar Flare Detection styling.

| Function | PAPER.md Reference | Description |
|---|---|---|
| `plot_xray_flux(times, flux, ax=None, **kwargs)` | §9.1, Figure 6 | Log-scale X-ray flux plot |
| `plot_rolling_variance(times, variance, L, ax=None, **kwargs)` | §9.2, Figure 7 | Rolling variance evolution |
| `plot_flare_overlay(times, flux, flare_times, flare_classes, ax=None, **kwargs)` | §9.3, Figure 8 | Flux + class-coded vertical lines |
| `add_regime_bands(ax, delta_phi_norm, times)` | §6.4 | Colored horizontal regime bands |
| `plot_delta_phi(times, delta_phi_norm, ax=None, **kwargs)` | §6.2, §6.4, Eq. (6) | Normalized ΔΦ(t) line plot with regime bands |
| `plot_psi_trajectory(phi, chi, times=None, ax=None, **kwargs)` | §7, §10.1, Eq. (7) | Phase–memory trajectory φ(t) vs χ(t) |
| `plot_composite_indicator(times, indicator, ax=None, **kwargs)` | §6.1, Eq. (5) | Composite instability indicator I(t) line plot |
| `style_solar_axes(ax, title=None, ylabel=None)` | — | Consistent grid / font styling |

**Module constant**

| Constant | Description |
|---|---|
| `FLARE_CLASS_COLORS` | `dict` mapping `"X"`, `"M"`, `"C"`, `"B"`, `"A"` → hex color strings |

**Import example**

```python
from shared.plot_utils import plot_xray_flux, plot_flare_overlay, FLARE_CLASS_COLORS
fig, ax = plot_xray_flux(times, flux)
fig, ax = plot_flare_overlay(times, flux, flare_times, flare_classes, ax=ax)
ax.set_title("GOES X-ray Flux with Events")
fig.savefig("output.png", dpi=150, bbox_inches="tight")
```

---

## Julia Modules

### `DataLoader.jl`

High-performance Julia counterpart to `data_loader.py`.  Provides typed, fully implemented functions for loading GOES data products from the NOAA SWPC JSON feeds (with local file-cache support).

| Function | Returns | GOES product |
|---|---|---|
| `load_xray_flux()` | NamedTuple `(times, flux)` | X-ray irradiance (1-min) |
| `load_xray_flares()` | NamedTuple `(time_begin, time_max, time_end, class_type, class_num)` | Flare event catalogue |
| `load_magnetometer()` | NamedTuple `(times, He)` | He-component magnetometer |
| `load_euvs()` | NamedTuple `(times, channels)` | EUV irradiance (multi-channel) |

**Import example**

```julia
include("shared/DataLoader.jl")
using .DataLoader
xray   = load_xray_flux()
flares = load_xray_flares()
```

---

### `MathUtils.jl`

Shared Julia mathematical utilities mirroring the pipeline-relevant parts of `math_utils.py`.  All functions accept and return `Vector{Float64}` and handle NaN values gracefully.

| Function | PAPER.md Reference | Description |
|---|---|---|
| `normalize_01(x)` | Eq. (5), Eq. (6) | Min-max normalization to [0, 1]; preserves NaN positions |
| `rolling_correlation(x, y, L)` | §6.2 | Rolling Pearson correlation C(t) over window of length L |

**Import example**

```julia
include("shared/MathUtils.jl")
using .MathUtils
x_norm = normalize_01(x)
C      = rolling_correlation(flux, euv, 30)
```

---

## Running the Python Test Suite

The `test/` directory at the repository root contains pytest-compatible unit tests for the shared modules:

| File | Covers |
|---|---|
| `test/test_math_utils.py` | All 8 functions in `math_utils.py` (43 tests) |
| `test/test_data_loader.py` | All 5 loader functions in `data_loader.py` (13 tests) |
| `test/test_plot_utils.py` | Smoke tests for all `plot_utils.py` functions (22 tests) |
| `test/test_integration_pipeline.py` | Full end-to-end pipeline integration test (synthetic data, no network) |

```bash
# From the repository root — install dependencies first if needed
pip install -r requirements.txt
pip install pytest

# Run all Python tests
pytest test/

# Run a specific module
pytest test/test_math_utils.py -v
pytest test/test_plot_utils.py -v
```
