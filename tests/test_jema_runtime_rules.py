"""
Static checks that wherewhen source stays importable inside a JEMA functional block.

jematools depends on wherewhen, so every wherewhen module has to follow the
JEMA sandbox rules too: Python 3.9 syntax, no ``__future__`` / ``os`` / ``sys`` /
``pathlib`` imports, and no PEP 604 unions in annotations (they are evaluated
at import time on 3.9 without ``from __future__ import annotations``).
Mirrors ``tests/test_jema_runtime_rules.py`` in jema-tools.
"""
import ast
import glob
import os

import pytest

PKG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "wherewhen")
SOURCES = sorted(glob.glob(os.path.join(PKG_DIR, "*.py")))

# Modules the JEMA sandbox refuses to import.
BANNED_MODULES = {"__future__", "os", "sys", "pathlib"}


def _tree(path, **kwargs):
    with open(path, encoding="utf-8") as fh:
        return ast.parse(fh.read(), filename=path, **kwargs)


def _ids(paths):
    return [os.path.basename(p) for p in paths]


def test_sources_found():
    assert SOURCES, f"no .py files under {PKG_DIR}"


@pytest.mark.parametrize("path", SOURCES, ids=_ids(SOURCES))
def test_parses_as_python_39(path):
    _tree(path, feature_version=(3, 9))


@pytest.mark.parametrize("path", SOURCES, ids=_ids(SOURCES))
def test_no_banned_imports(path):
    found = []
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            names = [node.module or ""]
        else:
            continue
        for name in names:
            if name.split(".")[0] in BANNED_MODULES:
                found.append(f"line {node.lineno}: {name}")
    assert not found, f"JEMA-banned imports in {os.path.basename(path)}: {found}"


def _annotations(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            for arg in args.posonlyargs + args.args + args.kwonlyargs + [args.vararg, args.kwarg]:
                if arg is not None and arg.annotation is not None:
                    yield arg.annotation
            if node.returns is not None:
                yield node.returns
        elif isinstance(node, ast.AnnAssign):
            yield node.annotation


@pytest.mark.parametrize("path", SOURCES, ids=_ids(SOURCES))
def test_no_pep604_unions_in_annotations(path):
    found = [
        f"line {ann.lineno}: {ast.unparse(ann)}"
        for ann in _annotations(_tree(path))
        if any(isinstance(n, ast.BinOp) and isinstance(n.op, ast.BitOr) for n in ast.walk(ann))
    ]
    assert not found, f"PEP 604 unions in {os.path.basename(path)}: {found}"


# Names that only make sense as types.  Set/dict unions (`frozenset(x) | {...}`,
# `dict(a) | kwargs`) and flag unions (`re.VERBOSE | re.IGNORECASE`) are valid
# 3.9 and must not match.
_TYPE_NAMES = {
    "int", "float", "complex", "str", "bytes", "bool", "object", "type",
    "list", "dict", "tuple", "set", "frozenset",
    "Any", "List", "Dict", "Tuple", "Set", "FrozenSet", "Optional", "Union",
    "Callable", "Iterable", "Iterator", "Sequence", "Mapping",
}


def _is_type_like(node):
    if isinstance(node, ast.Constant) and node.value is None:
        return True
    if isinstance(node, ast.Name):
        return node.id in _TYPE_NAMES
    if isinstance(node, ast.Subscript):
        return _is_type_like(node.value)
    if isinstance(node, ast.Attribute):  # typing.Optional[...]
        return node.attr in _TYPE_NAMES
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _is_type_like(node.left) or _is_type_like(node.right)
    return False


@pytest.mark.parametrize("path", SOURCES, ids=_ids(SOURCES))
def test_no_pep604_unions_outside_annotations(path):
    # `Opt = int | None` raises TypeError at import on 3.9 just like a hint does.
    found = [
        f"line {node.lineno}: {ast.unparse(node)}"
        for node in ast.walk(_tree(path))
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr) and _is_type_like(node)
    ]
    assert not found, f"PEP 604 unions in {os.path.basename(path)}: {found}"
