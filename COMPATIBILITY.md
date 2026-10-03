# wherewhen compatibility

`wherewhen` versions **independently** of jematools, h3tools, viztools and
tabtools. To avoid copies that go stale, this file states no version numbers.
Each fact lives in one place:

| Fact | Where it lives |
|---|---|
| This package's version | `wherewhen/_version.py` (`wherewhen.__version__`); history in [CHANGELOG.md](CHANGELOG.md) |
| What wherewhen requires | `dependencies` and `requires-python` in `pyproject.toml` (no toolkit dependencies) |
| What other packages require of wherewhen | each package's own `pyproject.toml` |
| Tested combinations and the current freeze | the toolkit matrix: `COMPATIBILITY.md` in the private workspace repo outsideken/geo-toolkit (`../COMPATIBILITY.md` in the workspace checkout) |

## Release checklist

1. Bump `wherewhen/_version.py` and the matching `version` in `pyproject.toml`.
   `tests/test_package.py` checks that they agree.
2. Move the `[Unreleased]` section of `CHANGELOG.md` to the new version, dated.
3. Update the hand-typed versions wherewhen#9 hasn't retired yet: the README
   version and test-count badges, and the title of
   `notebooks/01 CRS China and Russia.ipynb` (edit with nbformat).
4. After the release PR merges: tag `wherewhen-vX.Y.Z`.
5. Once the stack is verified, update the toolkit matrix in outsideken/geo-toolkit
   (current-freeze table and a dated row).
6. If new public APIs are added, bump a dependant's floor only when it starts
   calling them, then re-test the stack.
