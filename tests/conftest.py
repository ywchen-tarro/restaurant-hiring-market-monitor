"""Shared pytest helpers.

Tests import scraper.* — make sure the project root is on sys.path so they
work regardless of where pytest is invoked from.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def read_fixture(name: str) -> str:
    """Read a saved HTML fixture file."""
    p = FIXTURE_DIR / name
    return p.read_text(encoding="utf-8")
