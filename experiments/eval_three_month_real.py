"""
experiments/eval_three_month_real.py
=====================================
Run the precursor evaluation pipeline over the real GOES-18 3-month interval.

Uses the fixed date range 2024-01-01 — 2024-04-01 drawn from the real
GOES-18 XRS 1-minute dataset (``noaa_goes18_xrs_1m.csv.zip``).

Prerequisites
-------------
Run ``python shared/prepare_real_data.py`` once to populate the data cache
before executing this script.

Results are written to::

    results/eval_three_month_real.json

Usage
-----
::

    python experiments/eval_three_month_real.py [--n-shuffles N] [--random-state SEED]
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from experiments.run_interval_eval import run_interval_eval  # noqa: E402

# Fixed real-data interval: earliest 2024 timestamp as t0, 90-day window
_START = date(2024, 1, 1)
_END   = _START + timedelta(days=90)


def main(argv: "list[str] | None" = None) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate precursor signals over the real GOES-18 3-month interval "
            f"({_START} — {_END})."
        ),
    )
    parser.add_argument(
        "--n-shuffles",
        type=int,
        default=200,
        metavar="N",
        help="Number of shuffle-test permutations (default: 200).",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=None,
        metavar="SEED",
        help="RNG seed for reproducibility (default: None).",
    )
    args = parser.parse_args(argv)

    output = _REPO_ROOT / "results" / "eval_three_month_real.json"

    run_interval_eval(
        start=_START.isoformat(),
        end=_END.isoformat(),
        n_shuffles=args.n_shuffles,
        random_state=args.random_state,
        output=output,
    )


if __name__ == "__main__":
    main()
