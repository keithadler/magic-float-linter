"""Rewrite recognized literals in place - safely.

The overriding rule is: never corrupt a file. Every edit is located by
re-parsing the source and reading the AST node's own span, then verified
against the source text before it is applied; anything that does not verify
is skipped, not guessed at.

Two levels of fix:

- Safe (``--fix``): only literals whose suggestion evaluates, using ``math``
  alone, to a float bit-identical to the literal. These rewrites cannot change
  the program's numeric behavior; they only make an exact value readable.
- Truncated (``--fix-truncated``): table-tier truncated constants, where the
  rewrite deliberately *changes* the value to the more accurate exact form.
  Opt-in and reported as value changes.
"""

from __future__ import annotations

import ast
import math
import re
from collections import defaultdict
from dataclasses import dataclass

from .report import Finding

_OPERATOR_RE = re.compile(r"\s[-+*/]|\*\*")

_MATH_NAMESPACE = {"__builtins__": {}, "math": math}
_TRUNCATED_MAX_REL_ERROR = 1e-2  # sanity bound; the recognizer already matched


@dataclass
class FixResult:
    new_source: str
    applied: int
    skipped: int
    changes: list[tuple[int, str, str]]  # (line, old_text, new_text)


def _eval_math(expr: str) -> float | None:
    """Value of an expression that uses only ``math`` and literals, or None."""
    try:
        value = eval(expr, _MATH_NAMESPACE)  # noqa: S307 - namespace has no builtins
    except Exception:
        return None
    return float(value) if isinstance(value, (int, float)) else None


def _has_operator(expr: str) -> bool:
    # a top-level binary operator; table suggestions space theirs
    return _OPERATOR_RE.search(expr) is not None


def _imports_math(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(a.name == "math" for a in node.names):
            return True
    return False


def _import_insertion_line(tree: ast.Module) -> int:
    """1-based line after which `import math` should go (0 = file top)."""
    after = 0
    body = tree.body
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        after = body[0].end_lineno or 0
    for node in body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            after = max(after, node.end_lineno or 0)
    return after


def _replacement_for(finding: Finding, node: ast.Constant, parent: ast.AST | None,
                     fix_truncated: bool) -> str | None:
    """The exact replacement text for a literal, or None if it isn't fixable."""
    suggestion = finding.match.suggestion
    value = _eval_math(suggestion)
    if value is None:
        # references scipy/numpy or otherwise not math-evaluable: leave it,
        # rewriting would need an import we can't safely reason about
        return None
    if finding.match.truncated:
        if not (fix_truncated and finding.match.tier == "table"):
            return None
        literal_value = float(finding.literal.text)
        if literal_value == 0 or abs(value - literal_value) / abs(value) > _TRUNCATED_MAX_REL_ERROR:
            return None
    else:
        if value != float(finding.literal.text):
            return None
    if _has_operator(suggestion) and isinstance(parent, (ast.BinOp, ast.UnaryOp)):
        return f"({suggestion})"
    return suggestion


def fix_source(
    source: str, findings: list[Finding], fix_truncated: bool = False
) -> FixResult:
    """Apply fixes to one file's source. `findings` must all be for this file."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return FixResult(source, 0, len(findings), [])

    parents: dict[ast.AST, ast.AST] = {}
    nodes: dict[tuple[int, int], ast.Constant] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
        if isinstance(node, ast.Constant) and type(node.value) is float:
            nodes[(node.lineno, node.col_offset)] = node

    lines = source.splitlines(keepends=True)
    edits: dict[int, list[tuple[int, int, str]]] = defaultdict(list)
    changes: list[tuple[int, str, str]] = []
    applied = skipped = 0
    used_math = False

    for finding in findings:
        node = nodes.get((finding.literal.line, finding.literal.col))
        if node is None or node.end_lineno != node.lineno:
            skipped += 1
            continue
        replacement = _replacement_for(finding, node, parents.get(node), fix_truncated)
        if replacement is None:
            skipped += 1
            continue
        line = lines[node.lineno - 1]
        start, end = node.col_offset, node.end_col_offset
        original = line[start:end]
        # the safety net: only edit if the located span really is the literal
        if _eval_math(original) is None or float(original) != float(finding.literal.text):
            skipped += 1
            continue
        edits[node.lineno].append((start, end, replacement))
        changes.append((node.lineno, original, replacement))
        used_math = used_math or "math." in replacement
        applied += 1

    if applied == 0:
        return FixResult(source, 0, skipped, [])

    for lineno, line_edits in edits.items():
        line = lines[lineno - 1]
        for start, end, text in sorted(line_edits, key=lambda e: -e[0]):
            line = line[:start] + text + line[end:]
        lines[lineno - 1] = line
    new_source = "".join(lines)

    if used_math and not _imports_math(tree):
        insert_lines = new_source.splitlines(keepends=True)
        ending = "\r\n" if new_source[-2:] == "\r\n" else "\n"
        insert_lines.insert(_import_insertion_line(tree), f"import math{ending}")
        new_source = "".join(insert_lines)

    return FixResult(new_source, applied, skipped, changes)
