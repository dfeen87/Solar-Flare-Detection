"""
conftest.py — pytest configuration for the Solar Flare Detection test suite.

Ensures the repository root is on ``sys.path`` so that ``shared.*`` imports
work correctly when running ``pytest test/`` from any directory.
"""

import sys
from pathlib import Path

# Repository root is one level above this file (test/)
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
