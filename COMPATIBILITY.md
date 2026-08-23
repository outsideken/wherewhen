# wherewhen compatibility

`wherewhen` versions **independently** of jematools, h3tools, viztools, and
tabtools.  Dependents declare a minimum floor (e.g. `wherewhen>=0.2.6`) rather
than sharing a release number.

## This package

| Item | Value |
|---|---|
| **Current version** | `0.2.6` |
| **Toolkit dependencies** | none |
| **Python** | `>=3.9` |

## Downstream floors (typical)

| Consumer | Declares |
|---|---|
| jematools | `wherewhen>=0.2.0` |
| h3tools | `wherewhen>=0.2.6` |
| viztools | `wherewhen>=0.2.0` |
| tabtools | `wherewhen>=0.2.0` |

A fuller dated multi-package test matrix may live in a sibling toolkit
workspace.  This file is enough for a GitHub-only clone of `wherewhen`.

## Release checklist

1. Bump `wherewhen/_version.py`
2. Bump matching `version` in `pyproject.toml`
3. Add an entry to `CHANGELOG.md`
4. Sync README version / test-count badges
5. Git tag: `wherewhen-vX.Y.Z`
6. If new public APIs are added, bump dependent floors only when those packages
   start calling them — then re-test the stack
