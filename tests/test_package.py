"""
Tests for wherewhen package metadata and notification helpers.
"""
from __future__ import annotations

import pytest


class TestPackage:

    def test_version_string(self):
        import wherewhen
        assert wherewhen.__version__ == "0.2.6"

    def test_messages_warn_format(self):
        from wherewhen._messages import warn
        msg = warn("validate_latitude", "out of range.")
        assert msg.startswith("⚠️ [validate_latitude]")

    def test_messages_loaded_prints(self, capsys):
        from wherewhen._messages import loaded
        loaded("wherewhen", "0.2.1")
        out = capsys.readouterr().out
        assert "ℹ️ [wherewhen] v0.2.1 loaded." in out