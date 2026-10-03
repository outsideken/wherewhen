"""
Tests for wherewhen package metadata and notification helpers.
"""
from __future__ import annotations

import pytest


class TestPackage:

    def test_version_matches_pyproject(self):
        # One source of truth: _version.py and pyproject.toml must agree, so a
        # release bumps the version in those two places and nowhere else.
        import re
        from pathlib import Path

        import wherewhen
        pyproject = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")
        declared = re.search(r'^version = "([^"]+)"', pyproject, re.M).group(1)
        assert wherewhen.__version__ == declared

    def test_messages_warn_format(self):
        from wherewhen._messages import warn
        msg = warn("validate_latitude", "out of range.")
        assert msg.startswith("⚠️ [validate_latitude]")

    def test_messages_loaded_prints(self, capsys):
        from wherewhen._messages import loaded
        loaded("wherewhen", "0.2.1")
        out = capsys.readouterr().out
        assert "ℹ️ [wherewhen] v0.2.1 loaded." in out