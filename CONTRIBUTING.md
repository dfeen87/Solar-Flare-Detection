# Contributing to Solar Flare Detection

Thank you for your interest in contributing! This document explains how to set
up your environment, follow project conventions, run the test suite, and submit
a pull request.

---

## Development Environment

### Python

1. **Clone the repository** and change into its root directory.
2. **Create a virtual environment** (Python 3.9+ recommended):

   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   pip install pytest
   ```

### Julia

1. Install Julia 1.9+ from <https://julialang.org/downloads/>.
2. Each `tools/<domain>/` directory is an independent Julia project. Activate
   and instantiate as needed:

   ```bash
   cd tools/spiral_time
   julia --project -e "using Pkg; Pkg.instantiate()"
   ```

---

## Code Style

### Python

- Follow [PEP 8](https://peps.python.org/pep-0008/) for all Python code.
- Use descriptive variable names that match the scientific notation in
  `PAPER.md` where applicable (e.g. `delta_phi`, `chi_t`).
- Every public function must have a docstring.

### Julia

- Follow the [Julia style guide](https://docs.julialang.org/en/v1/manual/style-guide/).
- Type annotations are encouraged for function signatures.
- Every exported function must have a docstring.

---

## Running the Test Suite

### Python tests

```bash
# From the repository root
pytest test/

# Verbose output for a single module
pytest test/test_math_utils.py -v
pytest test/test_data_loader.py -v
pytest test/test_plot_utils.py -v

# End-to-end integration test (no network required)
pytest test/test_integration_pipeline.py -v
```

`test/conftest.py` automatically adds the repository root to `sys.path`.

### Julia tests

```bash
cd test
julia runtests.jl
```

---

## Adding a New Domain

Follow the pattern described in
[docs/how_to_navigate.md § "Adding a New Domain"](docs/how_to_navigate.md):

1. Create `domains/<name>/README.md` explaining the domain physics.
2. Add Python example(s) in `domains/<name>/examples_python/`.
3. Create `tools/<name>/<Name>.jl` with Julia stubs and a `Project.toml`.
4. Update `docs/overview.md` to describe the new domain.

Every new domain **must** include:

- A **Python educational layer** (`domains/<name>/examples_python/`) with at
  least one runnable demo script and corresponding pytest tests.
- A **Julia computational module** (`tools/<name>/`) that mirrors the Python
  math in a high-performance stub (function signatures + docstrings; full
  implementation may follow in a subsequent PR).
- Any required data fetched via `shared/data_loader.py` (which pulls from the NOAA SWPC API).

---

## Pull Request Expectations

- **Descriptive title** — briefly state what changed and why (e.g.
  `feat(topology): add Var_L[B] rolling-variance helper`).
- **Passing CI** — all Python and Julia tests must pass before merge.
- **Documentation** — new public functions, modules, or domains must be
  documented. Update `docs/overview.md` and `docs/how_to_navigate.md` as
  needed.
- **No generated artifacts** — do not commit files from `output/` or any
  `examples_python/output/` directory; these are covered by `.gitignore`.
- **Atomic commits** — each commit should represent a single logical change.
