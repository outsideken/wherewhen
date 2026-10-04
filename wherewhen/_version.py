"""
wherewhen._version
==================
Single source of truth for the package version.

Update this file when cutting a release; it is the only place the version is
typed.  ``pyproject.toml`` reads it (``dynamic = ["version"]``) and
``wherewhen/__init__.py`` imports from here.

Versions independently of jematools, h3tools, viztools, and tabtools.
See ``COMPATIBILITY.md`` and ``CHANGELOG.md`` in the toolkit workspace.
"""

__version__: str = "0.2.10"