"""
experiments/eval_one_month.py
==============================
Run the precursor evaluation pipeline for the most recent 1-month interval.

Calls ``run_interval_eval`` with start and end dates set to cover the
30-day period ending at the current UTC date.  Results are written to::

    results/eval_one_month.json

Usage
-----
::

    python experiments/eval_one_month.py [--n-shuffles N] [--random-state SEED]
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


def main(argv: "list[str] | None" = None) -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate precursor signals over the most recent 1-month interval.",
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

    end: date = date.today()
    start: date = end - timedelta(days=30)

    output = _REPO_ROOT / "results" / "eval_one_month.json"

    run_interval_eval(
        start=start.isoformat(),
        end=end.isoformat(),
        n_shuffles=args.n_shuffles,
        random_state=args.random_state,
        output=output,
    )


if __name__ == "__main__":
    main()
