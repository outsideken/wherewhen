"""
Every PDF tracked in this repo is built for the current version.

The same rule as h3-tools' ``tests/test_tracked_pdfs.py``: there, a hand-uploaded
``h3 Tools v 0.8.0b1.pdf`` sat beside a current Maths PDF for three releases.
The builder stamps the version into the PDF's title
(``c.setTitle(f"wherewhen Overview v{VERSION}")``), so a release PR that bumps
``wherewhen/_version.py`` without rebuilding the tracked PDF fails here. The
title is read from the file's plain ``/Title`` entry: no PDF library needed.
AGENTS.md "Releases" names the rebuild command.
"""

import re
import subprocess
from pathlib import Path
from typing import List, Optional

import pytest

import wherewhen

REPO = Path(__file__).resolve().parents[1]

# The PDFs the release rebuilds, and the builder that writes each one.
EXPECTED = {
    "wherewhen Overview.pdf": "scripts/build_overview_pdf.py",
}


def _tracked_pdfs() -> List[str]:
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO), "ls-files", "-z", "*.pdf"],
            check=True, capture_output=True, text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("needs a git checkout to list tracked files")
    return sorted(f for f in out.split("\0") if f)


def _title(path: Path) -> Optional[str]:
    match = re.search(rb"/Title \((.*?)\)", path.read_bytes())
    return match.group(1).decode("latin-1") if match else None


def test_only_the_rebuilt_pdfs_are_tracked():
    # A new PDF needs a builder and a line in EXPECTED, or it will go stale.
    assert _tracked_pdfs() == sorted(EXPECTED)


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_tracked_pdf_is_built_for_this_version(name):
    if name not in _tracked_pdfs():
        pytest.skip(f"{name} is not tracked here")
    title = _title(REPO / name)
    assert title is not None, f"{name} has no plain /Title entry"
    assert title.endswith(f"v{wherewhen.__version__}"), (
        f"{name} was built for {title!r}, not v{wherewhen.__version__}. "
        f"Rebuild it: ../.venv/bin/python {EXPECTED[name]} \"{name}\""
    )
