# wherewhen compatibility

`wherewhen` versions **independently** of jematools, h3tools, viztools, and
tabtools.  Dependents declare a minimum floor (e.g. `wherewhen>=0.2.8`).

## This package

| Item | Value |
|---|---|
| **Current version** | `0.2.9` |
| **Toolkit dependencies** | none |
| **Python** | `>=3.9` |

## Current freeze (with h3tools)

| Package | Version |
|---|---|
| wherewhen | **0.2.9** |
| viztools | **0.1.4** (`wherewhen>=0.2.0`) |
| h3tools | **0.9.0b2** (`wherewhen>=0.2.8`) |
| jematools | **0.6.0b3** (`wherewhen>=0.2.8`) |

See the toolkit workspace `COMPATIBILITY.md` for the full dated matrix.

## Release checklist

1. Bump `wherewhen/_version.py`
2. Bump matching `version` in `pyproject.toml`
3. Add an entry to `CHANGELOG.md`
4. Sync README version / test-count badges
5. Git tag: `wherewhen-vX.Y.Z`
6. If new public APIs are added, bump dependent floors only when those packages
   start calling them — then re-test the stack
