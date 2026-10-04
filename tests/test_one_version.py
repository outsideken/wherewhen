"""
The version is typed in one place: ``wherewhen/_version.py`` (#9).

K's one-source-of-truth rule (workspace ``AGENTS.md``): every other place reads
it (``pyproject.toml``) or says where to find it. These tests fail when a
hand-typed copy creeps back. Same tests as h3-tools' ``tests/test_one_version.py``.
"""

import json
import re
import subprocess
from pathlib import Path

import pytest

import wherewhen

REPO = Path(__file__).resolve().parents[1]

# Files allowed to contain the current version string, and why.
ALLOWED = {
    "wherewhen/_version.py",  # the one source
    "CHANGELOG.md",           # dated release history
}

VERSION_RE = re.compile(r"\d+\.\d+\.\d+(?:[ab]\d+|rc\d+)?")
# Dated history in notebook prose, e.g. "default since 0.2.3", "API note (v0.2.6)".
HISTORY_RE = re.compile(r"(?:since v?|note \(v)$")

BINARY = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".parquet", ".pkl", ".whl"}


def _tracked_files():
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO), "ls-files", "-z"], check=True, capture_output=True, text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("needs a git checkout to list tracked files")
    return [f for f in out.split("\0") if f]


def _sources(path: Path) -> str:
    """Text to scan: a notebook's cell sources (not its recorded outputs), or the file."""
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".ipynb":
        cells = json.loads(text)["cells"]
        return "\n".join("".join(c["source"]) if isinstance(c["source"], list) else c["source"] for c in cells)
    return text


def test_pyproject_reads_the_version_from_version_py():
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    project = re.search(r"^\[project\]\n(.*?)(?=^\[)", pyproject, re.M | re.S).group(1)
    assert not re.search(r"^version\s*=", project, re.M), "[project] must not type a version"
    assert re.search(r'^dynamic\s*=\s*\["version"\]', project, re.M)
    assert 'attr = "wherewhen._version.__version__"' in pyproject


def test_current_version_is_typed_only_where_allowed():
    version = wherewhen.__version__
    offenders = []
    for rel in _tracked_files():
        path = REPO / rel
        if rel in ALLOWED or path.suffix.lower() in BINARY or not path.is_file():
            continue
        try:
            if version in _sources(path):
                offenders.append(rel)
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    assert offenders == [], f"wherewhen {version} is hand-typed in {offenders}; say where to find it instead"


def test_notebooks_type_no_versions_except_dated_history():
    offenders = []
    for rel in _tracked_files():
        if not rel.endswith(".ipynb"):
            continue
        source = _sources(REPO / rel)
        for m in VERSION_RE.finditer(source):
            if not HISTORY_RE.search(source[max(0, m.start() - 10):m.start()]):
                offenders.append(f"{rel}: {source[max(0, m.start() - 30):m.end()]!r}")
    assert offenders == [], "\n".join(offenders)
