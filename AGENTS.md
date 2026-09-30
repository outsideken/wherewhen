# wherewhen

Workspace-wide rules (single checkout, GitHub installs, shared venv, how Claude and
Cursor work together) are in `../AGENTS.md`. This file covers wherewhen only.

## What it is

The shared "where" and "when" primitives for the toolkit: coordinate parsing and
formatting, geodesic math, datetime handling, solar/lunar data, and CRS conversions.
h3tools, jematools and viztools all depend on it, so a change here reaches all three.

## Layout

- `wherewhen/` — the package: `geometry.py`, `temporal.py`, `crs.py`, plus
  `_validators.py`, `_messages.py` (message formatting shared with jematools) and
  `_version.py`.
- `tests/` — pytest suite. `test_jema_runtime_rules.py` enforces the JEMA rules below.
  CI (`.github/workflows/ci.yml`) runs everything on Python 3.12 and 3.9 and
  validates notebooks.
- `notebooks/` — `01 CRS China and Russia.ipynb` (small demo CSVs in `00 data/`).
- `CHANGELOG.md` — record every user-visible change under `[Unreleased]`.

## Rules

- **JEMA-safe.** jematools imports wherewhen inside JEMA, and K's rule is to treat that
  code as user code (outsideken/JEMA-Tools#2). So: Python 3.9 syntax, no `__future__`,
  `os`, `sys` or `pathlib` imports, and no `X | Y` type unions. Details in
  `jema-tools/AGENTS.md`. Tests may use anything.
- **Downstream effect.** h3-tools and jema-tools CI install wherewhen from GitHub
  `main`. Before merging, run the dependants' suites against your branch, e.g. from
  `../jema-tools`: `PYTHONPATH=../wherewhen ../.venv/bin/python -m pytest -q`.
- **Releases** follow the checklist in `COMPATIBILITY.md` (version in `_version.py` and
  `pyproject.toml`, `CHANGELOG.md`, README badges).

## Testing

`../.venv/bin/python -m pytest -q` from the repo root (under a second).

## Open work

Track to-dos as GitHub issues on outsideken/wherewhen, claimed with the
`agent:claude` / `agent:cursor` labels.
