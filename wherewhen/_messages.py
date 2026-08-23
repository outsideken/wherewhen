"""
wherewhen._messages
===================
Shared notification helpers for errors, warnings, and status messages.

Emoji prefix convention (aligned with jematools):

⚠️  validation error or invalid input
ℹ️  informational notice (non-fatal)
❌  operation skipped or not supported
✏️  user input / configuration note
✅  success (verbose logging)

Import-time load notices use :func:`loaded` — printed once when a package's
``__init__`` is first imported:

    ℹ️ [wherewhen] v<version> loaded.
"""

from __future__ import annotations


def warn(func: str, msg: str) -> str:
    """Format a validation or usage error message."""
    return f"⚠️ [{func}] {msg}"


def info(func: str, msg: str) -> str:
    """Format an informational message."""
    return f"ℹ️ [{func}] {msg}"


def skip(func: str, msg: str) -> str:
    """Format a skipped-operation message."""
    return f"❌ [{func}] {msg}"


def note(func: str, msg: str) -> str:
    """Format a configuration or input note."""
    return f"✏️ [{func}] {msg}"


def ok(func: str, msg: str) -> str:
    """Format a success message."""
    return f"✅ [{func}] {msg}"


def loaded(package: str, version: str) -> None:
    """Print the standard toolkit import-time load notice."""
    print(info(package, f"v{version} loaded."))