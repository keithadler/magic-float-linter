"""Extract float literals, with context, from Python source files."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

_NUMERIC = (int, float)
_CONTAINERS = (ast.List, ast.Tuple, ast.Set, ast.Dict)
_NESTED_SEQUENCE_SIZE = 1_000_000  # sentinel: always over the data-sequence threshold
_SUPPRESS_RE = re.compile(r"#\s*exact:\s*ignore\b")


@dataclass
class FloatLiteral:
    """A float literal as it appears in source, before any interpretation."""

    text: str  # exact source text, e.g. "0.017453292519943295"
    file: Path
    line: int
    col: int
    context: str = ""  # nearest name binding (variable, keyword, default arg), if any
    sequence_size: int = field(default=0)  # numeric elements in the enclosing list/tuple/set
    suppressed: bool = False  # silenced by a "# exact: ignore" comment
    op: str = ""  # enclosing binary operation: "mul", "div-num", "div-den", "add", "sub"
    other_operand: str = ""  # source text of the other operand, when it is a simple name


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
    # A short tuple/list nested inside another container (a list of RGB
    # triples, a dict of coordinate pairs) is a data table entry even though
    # it's short itself - e.g. matplotlib's colormap tables are lists of
    # 3-element lists, well under the plain short-sequence threshold alone.
    if isinstance(parents.get(parent), _CONTAINERS):
        return _NESTED_SEQUENCE_SIZE
    count = 0
    for elt in parent.elts:
        if isinstance(elt, ast.UnaryOp):
            elt = elt.operand
        if isinstance(elt, ast.Constant) and type(elt.value) in _NUMERIC:
            count += 1
    return count


_BINOP_NAMES = {ast.Mult: "mul", ast.Add: "add", ast.Sub: "sub"}


def _operation(
    node: ast.AST, parents: dict[ast.AST, ast.AST], source: str
) -> tuple[str, str]:
    """The binary operation enclosing the literal, and the other operand's
    source text when that operand is a simple name or attribute."""
    parent = parents.get(node)
    if isinstance(parent, ast.UnaryOp):  # look through a leading minus
        node, parent = parent, parents.get(parent)
    if not isinstance(parent, ast.BinOp):
        return "", ""
    if isinstance(parent.op, ast.Div):
        op = "div-num" if parent.left is node else "div-den"
    else:
        op = _BINOP_NAMES.get(type(parent.op), "")
        if not op:
            return "", ""
    other = parent.right if parent.left is node else parent.left
    if isinstance(other, (ast.Name, ast.Attribute)):
        return op, ast.get_source_segment(source, other) or ""
    return op, ""


def _is_suppressed(lineno: int, lines: list[str]) -> bool:
    """A literal is suppressed by a trailing comment on its own line, or by a
    comment-only line directly above it."""
    own_line = lines[lineno - 1] if 0 < lineno <= len(lines) else ""
    if _SUPPRESS_RE.search(own_line):
        return True
    prev_line = lines[lineno - 2].strip() if lineno >= 2 else ""
    return prev_line.startswith("#") and bool(_SUPPRESS_RE.search(prev_line))


def extract_source(source: str, file: Path) -> list[FloatLiteral]:
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return []
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    lines = source.splitlines()
    literals: list[FloatLiteral] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and type(node.value) is float:
            text = ast.get_source_segment(source, node) or repr(node.value)
            op, other_operand = _operation(node, parents, source)
            literals.append(
                FloatLiteral(
                    text=text.strip("()"),
                    file=file,
                    line=node.lineno,
                    col=node.col_offset,
                    context=_context_for(node, parents),
                    sequence_size=_sequence_size(node, parents),
                    suppressed=_is_suppressed(node.lineno, lines),
                    op=op,
                    other_operand=other_operand,
                )
            )
    return literals


def extract_file(path: Path) -> list[FloatLiteral]:
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return extract_source(source, path)
