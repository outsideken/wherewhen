"""
wherewhen._messages
===================
Shared notification helpers for errors, warnings, and status messages.

Emoji prefix convention (aligned with jematools):

⚠️  every raised error: invalid input, or a missing optional package
ℹ️  informational notice (non-fatal)
❌  printed notice: an item was skipped (never used for raised errors)
✏️  user input / configuration note
✅  success (verbose logging)

Import-time load notices use :func:`loaded` — printed once when a package's
``__init__`` is first imported:

    ℹ️ [wherewhen] v<version> loaded.

:func:`named_errors` is the one copy of the decorator that points a toolkit
error's ``[label]`` at the public function the user called. h3tools, jematools
and viztools import it from here once they drop their own copies.
"""
import functools
import re


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


# "⚠️ [label] text" / "❌ [label] text": the toolkit's message prefix.
_LABEL = re.compile(r"^(\S+ )\[[A-Za-z_][A-Za-z0-9_]*\]")


def _relabel(exc: BaseException, func_name: str) -> None:
    """Point a toolkit error's ``[label]`` at *func_name*, in place."""
    if not (exc.args and isinstance(exc.args[0], str)):
        return
    original = exc.args[0]
    relabelled = _LABEL.sub(lambda m: f"{m.group(1)}[{func_name}]", original, count=1)
    if relabelled == original:
        return
    exc.args = (relabelled,) + exc.args[1:]
    # ImportError (and subclasses) print .msg, not args.
    if getattr(exc, "msg", None) == original:
        exc.msg = relabelled


def named_errors(func):
    """
    Decorate a public function so its toolkit errors name it.

    A labelled error (``⚠️ [x] …`` / ``❌ [x] …``) escaping *func*, from its own
    checks, a helper, another public function or wherewhen, is relabelled
    ``[func.__name__]`` and the same exception object is re-raised (class,
    traceback and the rest of the message unchanged).  Nested public calls
    relabel on the way out, so the error names the outermost function, which
    is the one the user called.  Unlabelled errors pass through untouched.
    """
    name = func.__name__

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            _relabel(exc, name)
            raise

    for attr in ("cache_info", "cache_clear"):  # keep lru_cache's helpers reachable
        if hasattr(func, attr):
            setattr(wrapper, attr, getattr(func, attr))
    return wrapper