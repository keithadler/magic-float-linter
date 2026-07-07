"""Context-aware idiomatic rewrites.

When the extractor knows how a literal is used (multiplied by a simple name,
used as a denominator), some suggestions have a more idiomatic form than
substituting the exact constant: `x * 0.017453292519943295` is
`math.radians(x)`, not `x * (math.pi / 180)`.

Every rule here must be an exact algebraic identity of the enclosing
expression. Rules that would only hold under an assumption about the operand
are deliberately absent: `x * (1/ln 2)` equals log2(e**x), not log2(x), so
rewriting it as `math.log2(x)` would be wrong unless x is already a natural
log - something we cannot know. For those, the constant's table note (e.g.
"log base-2 conversion: prefer math.log2(x)") gives the human the hint and
leaves the judgment to them.
"""

from __future__ import annotations

from .extract import FloatLiteral
from .recognize import Match

# (form, op) -> template over the other operand; exact identities only
_RULES: dict[tuple[str, str], str] = {
    # x * pi/180 == radians(x); x / (pi/180) == degrees(x); and mirrored
    ("pi/180", "mul"): "math.radians({other})",
    ("pi/180", "div-den"): "math.degrees({other})",
    ("180/pi", "mul"): "math.degrees({other})",
    ("180/pi", "div-den"): "math.radians({other})",
    # tau reads better than a two-pi literal in a product or denominator
    ("2*pi", "mul"): "math.tau * {other}",
    ("2*pi", "div-den"): "{other} / math.tau",
    ("1/(2*pi)", "mul"): "{other} / math.tau",
}


def idiomatic(match: Match, literal: FloatLiteral) -> str | None:
    """An idiomatic replacement for the literal's whole enclosing operation,
    or None when no rule applies. Note the returned expression replaces the
    entire `<other> <op> <literal>` expression, not just the literal."""
    if not literal.other_operand:
        return None
    template = _RULES.get((match.form, literal.op))
    if template is None:
        return None
    return template.format(other=literal.other_operand)
