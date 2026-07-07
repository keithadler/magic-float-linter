"""Extract float literals, with context, from Python source files."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

_NUMERIC = (int, float)


@dataclass
class FloatLiteral:
    """A float literal as it appears in source, before any interpretation."""

    text: str  # exact source text, e.g. "0.017453292519943295"
    file: Path
    line: int
    col: int
    context: str = ""  # nearest name binding (variable, keyword, default arg), if any
    sequence_size: int = field(default=0)  # numeric elements in the enclosing list/tuple/set


def _context_for(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> str:
    cur: ast.AST | None = node
    for _ in range(6):
        parent = parents.get(cur)
        if parent is None:
            return ""
        if isinstance(parent, ast.keyword) and parent.arg:
            return parent.arg
        if (
            isinstance(parent, ast.Assign)
            and len(parent.targets) == 1
            and isinstance(parent.targets[0], ast.Name)
        ):
            return parent.targets[0].id
        if isinstance(parent, ast.AnnAssign) and isinstance(parent.target, ast.Name):
            return parent.target.id
        if isinstance(parent, ast.arguments):
            positional = parent.posonlyargs + parent.args
            for default, arg in zip(reversed(parent.defaults), reversed(positional)):
                if default is cur:
                    return arg.arg
            for default, arg in zip(parent.kw_defaults, parent.kwonlyargs):
                if default is cur:
                    return arg.arg
            return ""
        if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
            return ""
        cur = parent
    return ""


def _sequence_size(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> int:
    parent = parents.get(node)
    if isinstance(parent, ast.UnaryOp):  # look through a leading minus
        node, parent = parent, parents.get(parent)
    if not isinstance(parent, (ast.List, ast.Tuple, ast.Set)):
        return 0
    count = 0
    for elt in parent.elts:
        if isinstance(elt, ast.UnaryOp):
            elt = elt.operand
        if isinstance(elt, ast.Constant) and type(elt.value) in _NUMERIC:
            count += 1
    return count


def extract_source(source: str, file: Path) -> list[FloatLiteral]:
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return []
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    literals: list[FloatLiteral] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and type(node.value) is float:
            text = ast.get_source_segment(source, node) or repr(node.value)
            literals.append(
                FloatLiteral(
                    text=text.strip("()"),
                    file=file,
                    line=node.lineno,
                    col=node.col_offset,
                    context=_context_for(node, parents),
                    sequence_size=_sequence_size(node, parents),
                )
            )
    return literals


def extract_file(path: Path) -> list[FloatLiteral]:
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return extract_source(source, path)
