"""
Facts the overview PDF prints, read from this checkout so they can't go stale.

Every number a reader sees (version, test count, function counts) comes from
the package or a live test run, never from a constant typed into the builder.
If a fact can't be read, the build stops instead of printing a guess. Same
pattern as h3-tools' and jema-tools' ``scripts/_pdf_facts.py``.
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
# Describe the code in this checkout, not whatever copy is installed.
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

# Helpers identical across the PDF builders live in the workspace repo
# (outsideken/geo-toolkit, scripts/pdf_facts.py). They take the repo as an
# argument, and this file always passes its own checkout.
_WORKSPACE_SCRIPTS = REPO.parent / "scripts"
if not (_WORKSPACE_SCRIPTS / "pdf_facts.py").exists():
    raise SystemExit(f"PDF facts: needs the geo-toolkit workspace checkout: {_WORKSPACE_SCRIPTS / 'pdf_facts.py'} not found")
sys.path.insert(0, str(_WORKSPACE_SCRIPTS))
import pdf_facts as _shared  # noqa: E402

fail = _shared.fail
number_word = _shared.number_word

# Where the builder writes the PDF unless given a path: the workspace's
# git-ignored reports/ folder, next to this repo.
REPORTS = REPO.parent / "reports"


def passing_tests() -> int:
    """Run this checkout's suite and return the passed count; stop if anything fails."""
    return _shared.passing_tests(REPO)


def public_functions(pkg) -> set:
    """Public functions on *pkg*, minus helpers defined in its ``__init__``.

    ``inspect.unwrap`` sees through ``lru_cache`` (``get_solar_data`` and
    ``get_lunar_data`` are cached), which ``inspect.isfunction`` alone misses.
    """
    names = set()
    for name in dir(pkg):
        obj = getattr(pkg, name)
        if name.startswith("_") or not inspect.isfunction(inspect.unwrap(obj)):
            continue
        if obj.__module__ != pkg.__name__:
            names.add(name)
    return names
