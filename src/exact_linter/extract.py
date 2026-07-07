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
class FileInfo:
    """Literals plus the import context suggestions should be rendered in."""

    literals: list[FloatLiteral]
    sequences: list[NumericSequence] = field(default_factory=list)
    math_names: frozenset[str] = frozenset()  # from math import <name>, ...
    modules: frozenset[str] = frozenset()  # top-level modules imported


@dataclass
class NumericSequence:
    """A flat list/tuple/set literal of pure numeric elements - a candidate
    for whole-sequence recognition (see sequences.py: is every element an
    exact rational or known constant, e.g. a Runge-Kutta weight vector?).

    Individual elements inside a long sequence are also still extracted as
    ordinary FloatLiteral objects and skipped by triage ("inside a numeric
    data sequence") - this is a second, independent view of the same source
    for a different kind of check, not a replacement for that skip.
    """

    elements: list[str]  # source text of each element, in order
    file: Path
    line: int
    col: int


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


def _float_parseable(text: str | None) -> str | None:
    """`text` if Python's float() can parse it, else None.

    An int constant is captured here too (see _sequence_element_text), so
    its source text can be any int literal form: decimal ("42"), but also
    hex/octal/binary ("0x3c00", a float16 bit pattern in a lookup table -
    the real case this guard exists for). float() only understands decimal
    text; passing it hex-int text raises ValueError deep inside downstream
    code (recognize()) that assumes every string it receives is already
    known-parseable. Rejecting here means the *whole* enclosing sequence is
    left uncaptured, matching how any other non-numeric element is handled -
    not a partial, silently-wrong capture.
    """
    if text is None:
        return None
    try:
        float(text)
    except ValueError:
        return None
    return text


def _sequence_element_text(elt: ast.expr, source: str) -> str | None:
    """Source text of `elt` if it is a plain numeric literal (int/float,
    optionally sign-prefixed) whose text float() can parse, else None -
    signaling "not a pure numeric sequence" to the caller, which then skips
    capturing the whole container."""
    node = elt
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        inner = node.operand
        if isinstance(inner, ast.Constant) and type(inner.value) in _NUMERIC:
            return _float_parseable(ast.get_source_segment(source, node))
        return None
    if isinstance(node, ast.Constant) and type(node.value) in _NUMERIC:
        return _float_parseable(ast.get_source_segment(source, node))
    return None


def _extract_sequences(
    tree: ast.AST, parents: dict[ast.AST, ast.AST], source: str, file: Path
) -> list[NumericSequence]:
    sequences: list[NumericSequence] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.List, ast.Tuple, ast.Set)) or not node.elts:
            continue
        # a short list/tuple nested inside another container (a list of RGB
        # triples, a dict of coordinate pairs) is a data-table row, not a
        # coefficient vector to name as a unit - same exclusion as
        # _sequence_size uses for the per-element "inside a data sequence" skip
        if isinstance(parents.get(node), _CONTAINERS):
            continue
        elements: list[str] = []
        for elt in node.elts:
            text = _sequence_element_text(elt, source)
            if text is None:
                elements = []
                break
            elements.append(text)
        if elements:
            sequences.append(
                NumericSequence(elements=elements, file=file, line=node.lineno, col=node.col_offset)
            )
    return sequences


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


def _collect_imports(tree: ast.AST) -> tuple[frozenset[str], frozenset[str]]:
    math_names: set[str] = set()
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module.split(".")[0])
            if node.module == "math":
                math_names.update(alias.name for alias in node.names)
    return frozenset(math_names), frozenset(modules)


def extract_source_info(source: str, file: Path) -> FileInfo:
    """Like extract_source, but also reports numeric sequences and the
    file's import context."""
    literals = extract_source(source, file)
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return FileInfo(literals)
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    sequences = _extract_sequences(tree, parents, source, file)
    math_names, modules = _collect_imports(tree)
    return FileInfo(literals, sequences=sequences, math_names=math_names, modules=modules)


def extract_file_info(path: Path) -> FileInfo:
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return FileInfo([])
    return extract_source_info(source, path)
