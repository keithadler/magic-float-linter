"""Recognition engine: table lookup, then rational check, then PSLQ search."""

from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction

import mpmath

from . import confidence
from .constants import table
from .triage import significant_digits

PSLQ_MIN_DIGITS = 10  # PSLQ combos need strong evidence; skip short literals
PSLQ_CONSTANTS = ("pi", "e", "ln(2)", "sqrt(2)", "sqrt(3)")
MAX_RATIONAL_DENOMINATOR = 10_000


@dataclass
class Match:
    form: str  # exact form, e.g. "pi/180"
    suggestion: str  # replacement code, e.g. "math.pi / 180"
    note: str
    tier: str  # "table" | "rational" | "pslq"
    matched_digits: int
    surplus: float


def _agrees(x: mpmath.mpf, y: mpmath.mpf, digits: int) -> bool:
    if y == 0:
        return False
    return abs(x - y) <= abs(y) * mpmath.mpf(10) ** (1 - digits)


def _match_table(x: mpmath.mpf, digits: int) -> Match | None:
    for value, entry in table():
        if _agrees(x, value, digits):
            return Match(
                form=entry.form,
                suggestion=entry.suggestion,
                note=entry.note,
                tier="table",
                matched_digits=digits,
                surplus=confidence.table_surplus(digits),
            )
    return None


def _match_rational(x: mpmath.mpf, digits: int) -> Match | None:
    frac = Fraction(float(x)).limit_denominator(MAX_RATIONAL_DENOMINATOR)
    if frac.denominator == 1:
        return None
    if not _agrees(x, mpmath.mpf(frac.numerator) / frac.denominator, digits):
        return None
    reduced = frac.denominator
    for factor in (2, 5):
        while reduced % factor == 0:
            reduced //= factor
    if reduced == 1:
        # terminating decimal (denominator has only 2s and 5s), e.g. 0.125:
        # exactly representable, almost always intentional
        return None
    return Match(
        form=f"{frac.numerator}/{frac.denominator}",
        suggestion=f"{frac.numerator} / {frac.denominator}",
        note="repeating decimal",
        tier="rational",
        matched_digits=digits,
        surplus=confidence.rational_surplus(digits, frac.numerator, frac.denominator),
    )


_PY_REWRITES = (
    (re.compile(r"\bsqrt\("), "math.sqrt("),
    (re.compile(r"\bcbrt\("), "math.cbrt("),
    (re.compile(r"\bln\("), "math.log("),
    (re.compile(r"\bexp\("), "math.exp("),
    (re.compile(r"\bpi\b"), "math.pi"),
    (re.compile(r"\be\b"), "math.e"),
)


def _to_python(expr: str) -> str:
    out = expr
    for pattern, replacement in _PY_REWRITES:
        out = pattern.sub(replacement, out)
    return out


def _match_pslq(x: mpmath.mpf, digits: int) -> Match | None:
    if digits < PSLQ_MIN_DIGITS:
        return None
    # mpmath's PSLQ needs at least 53 bits of working precision; the tol
    # argument still limits claims to the evidence the literal provides
    with mpmath.workdps(max(digits, 16)):
        try:
            found = mpmath.identify(
                x, constants=PSLQ_CONSTANTS, tol=mpmath.mpf(10) ** (2 - digits)
            )
        except ValueError:
            return None
    if not found:
        return None
    if not re.search(r"[a-zA-Z]", found):
        # a pure rational: that verdict belongs to the rational tier, which
        # already declined (terminating decimal or not enough evidence)
        return None
    namespace = {
        name: getattr(mpmath, name) for name in ("pi", "e", "sqrt", "cbrt", "ln", "exp", "log")
    }
    with mpmath.workdps(digits + 20):
        try:
            value = mpmath.mpf(eval(found, {"__builtins__": {}}, namespace))
        except Exception:
            return None
        if not _agrees(x, value, digits):
            return None
    return Match(
        form=found,
        suggestion=_to_python(found),
        note="found by PSLQ search",
        tier="pslq",
        matched_digits=digits,
        surplus=confidence.pslq_surplus(digits, found),
    )


def recognize(text: str, min_surplus: float = confidence.DEFAULT_MIN_SURPLUS) -> Match | None:
    """Try to recognize a float literal (given as source text) as an exact form."""
    digits = significant_digits(text)
    with mpmath.workdps(max(digits, 15) + 25):
        x = mpmath.mpf(text.replace("_", ""))
        for finder in (_match_table, _match_rational, _match_pslq):
            match = finder(x, digits)
            if match is not None and match.surplus >= min_surplus:
                return match
    return None
