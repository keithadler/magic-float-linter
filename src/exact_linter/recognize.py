"""Recognition engine: table lookup, then rational check, then PSLQ search.

Beyond naming a constant, the engine also measures how much numerical
accuracy a literal *loses* by being written out as a short decimal instead
of the exact form. A literal like 3.14159 names pi but is only accurate to
six digits inside a double that holds sixteen; that lost precision is often
a real bug, and it is reported as a truncation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache

import mpmath

from . import confidence
from .constants import ConstantEntry, table
from .triage import significant_digits

PSLQ_MIN_DIGITS = 10  # PSLQ combos need strong evidence; skip short literals
PSLQ_CONSTANTS = ("pi", "e", "ln(2)", "sqrt(2)", "sqrt(3)")
MAX_RATIONAL_DENOMINATOR = 10_000

LOGSPACE_MIN_DIGITS = 11
# 2, 3, 5, 7, 11, pi: independent primes plus pi. Deliberately excludes 10
# (=2*5) - including it creates a built-in linear dependency
# (ln10 - ln2 - ln5 = 0) that PSLQ finds instead of any real relation
# involving x. Widened from {2,3,5} to include 7 and 11 after the corpus
# study found a real, human-documented miss needing exactly those primes
# (astropy's neutrino energy-density correction, 7/8 * (4/11)**(4/3));
# empirically re-checked against 2000+ random numbers per digit count near
# LOGSPACE_MIN_DIGITS and the false-positive rate stayed at 0, so no
# confidence charge increase was needed for the wider search.
LOGSPACE_BASES = (2, 3, 5, 7, 11)

# A Python float carries about this many significant decimal digits
# (53 * log10(2)). A literal accurate to fewer digits than the exact form
# would give has lost precision.
DOUBLE_DIGITS = 15.95
TRUNCATION_MIN_LOST = 3  # report truncation once this many digits are lost

# Near-miss (typo) detection applies only to short, plausibly hand-typed
# literals. A value written to near-full double precision that sits a
# unit-in-the-last-place off a constant is a machine-precision artifact, not
# a typo, so cap the digits a near-miss may have.
NEAR_MISS_MAX_DIGITS = 12


@dataclass(frozen=True)
class Match:
    form: str  # exact form, e.g. "pi/180"
    suggestion: str  # replacement code, e.g. "math.pi / 180"
    note: str
    tier: str  # "table" | "rational" | "pslq" | "logspace"
    matched_digits: int
    surplus: float
    precision_lost: int = 0  # digits of accuracy lost vs. the exact form
    # a literal close to a known constant but NOT its correct rounding: a
    # written digit is actually wrong (e.g. 2.71827 for e). Likely a typo,
    # not an honest truncation.
    near_miss: bool = False

    @property
    def truncated(self) -> bool:
        # a near-miss is a wrong value, not a faithful-but-short one; don't
        # also label it a truncation
        return self.precision_lost >= TRUNCATION_MIN_LOST and not self.near_miss

    @property
    def code(self) -> str:
        """Stable finding category for --select/--ignore and per-line
        "# exact: ignore[code]" suppression. Every Match falls into exactly
        one of these three (near-miss and truncated are mutually exclusive
        by construction - see `truncated` above); whole-sequence findings
        (sequences.py) are always "sequence", the fourth code."""
        if self.near_miss:
            return "near-miss"
        if self.truncated:
            return "truncated"
        return "recognized"


def _agrees(x: mpmath.mpf, y: mpmath.mpf, digits: int) -> bool:
    if y == 0:
        return False
    return abs(x - y) <= abs(y) * mpmath.mpf(10) ** (1 - digits)


def _precision_lost(x: mpmath.mpf, true_value: mpmath.mpf) -> int:
    """Digits of accuracy the literal x loses relative to the exact value."""
    if true_value == 0:
        return 0
    rel = abs(x - true_value) / abs(true_value)
    if rel == 0:
        return 0
    accuracy = -mpmath.log10(rel)
    lost = DOUBLE_DIGITS - accuracy
    return max(0, int(mpmath.floor(lost + mpmath.mpf("0.5"))))


def _sigfig_scale(v: mpmath.mpf, digits: int) -> mpmath.mpf:
    exp = int(mpmath.floor(mpmath.log10(abs(v))))
    return mpmath.mpf(10) ** (digits - 1 - exp)


def _round_sigfigs(v: mpmath.mpf, digits: int) -> mpmath.mpf:
    """v rounded to `digits` significant figures."""
    if v == 0:
        return mpmath.mpf(0)
    scale = _sigfig_scale(v, digits)
    return mpmath.nint(v * scale) / scale


def _trunc_sigfigs(v: mpmath.mpf, digits: int) -> mpmath.mpf:
    """v truncated (chopped toward zero) to `digits` significant figures."""
    if v == 0:
        return mpmath.mpf(0)
    scale = _sigfig_scale(v, digits)
    return mpmath.mpf(int(v * scale)) / scale


def _is_near_miss(x: mpmath.mpf, true_value: mpmath.mpf, digits: int) -> bool:
    """True if x is close to true_value (close enough to have matched) but is
    a *wrong* rendering of it - a written digit is actually incorrect. That is
    the signature of a typo or transcription error (2.71827 for e), as opposed
    to a faithful short rendering.

    A rendering is faithful if it is the constant rounded OR truncated
    (chopped) to the digits written, or if it is simply the nearest double to
    the constant (a full-precision literal, whose decimal repr can differ from
    the true value's own rounding in the last place).

    Only short literals qualify: a near-full-precision value a unit-in-the-
    last-place off a constant is a machine artifact, not a typo. Callers also
    restrict this to mathematical constants - physical constants have legit
    historical revisions that look like typos of the current value.
    """
    if true_value == 0 or digits > NEAR_MISS_MAX_DIGITS:
        return False
    if float(x) == float(true_value):
        return False
    tol = abs(true_value) * mpmath.mpf(10) ** (mpmath.mpf("0.5") - digits)
    if abs(x - _round_sigfigs(true_value, digits)) <= tol:
        return False
    if abs(x - _trunc_sigfigs(true_value, digits)) <= tol:
        return False
    return True


def _needs_parens(suggestion: str) -> bool:
    """True if using the suggestion as a denominator needs parentheses.

    A bare name or a single function call is safe (`1 / math.sqrt(5)`); a
    top-level binary operator is not (`1 / (math.sqrt(2) / 2)`). Table
    suggestions always space their binary operators, so their presence is
    the signal.
    """
    return re.search(r"\s[-+*/]|\*\*", suggestion) is not None


def _match_table(
    x: mpmath.mpf, digits: int, extra: tuple[ConstantEntry, ...] = ()
) -> Match | None:
    rows = table(extra)
    # Pick the closest agreeing entry, not the first in table order: some
    # constants sit within each other's tolerance window at low precision
    # (a superseded CODATA value can be within the current value's matching
    # tolerance, and vice versa), and the literal should be attributed to
    # whichever it actually equals, not whichever happens to be listed first.
    best: tuple[mpmath.mpf, ConstantEntry] | None = None
    for value, entry in rows:
        if _agrees(x, value, digits) and (best is None or abs(x - value) < abs(x - best[0])):
            best = (value, entry)
    if best is not None:
        value, entry = best
        return Match(
            form=entry.form,
            suggestion=entry.suggestion,
            note=entry.note,
            tier="table",
            matched_digits=digits,
            surplus=confidence.table_surplus(digits, len(rows)),
            precision_lost=_precision_lost(x, value),
            near_miss=entry.decimal is None and _is_near_miss(x, value, digits),
        )
    # Reciprocal folding: a literal may be 1/entry for an entry we listed
    # only in its plain form. This extends the table's reach to every
    # reciprocal for free, at a small confidence charge for the wider search.
    if x != 0:
        recip = 1 / x
        for value, entry in rows:
            if _agrees(recip, value, digits):
                true_value = 1 / value
                sugg = (
                    f"({entry.suggestion})"
                    if _needs_parens(entry.suggestion)
                    else entry.suggestion
                )
                return Match(
                    form=f"1/({entry.form})",
                    suggestion=f"1 / {sugg}",
                    note=entry.note,
                    tier="table",
                    matched_digits=digits,
                    surplus=confidence.table_surplus(digits, len(rows))
                    - confidence.FOLD_PENALTY,
                    precision_lost=_precision_lost(x, true_value),
                    near_miss=entry.decimal is None and _is_near_miss(x, true_value, digits),
                )
    # Complement folding (1 - entry, e.g. exponential-saturation constants
    # like 1 - 1/e) and shift folding (entry + 1, e.g. a root shifted up by
    # one), restricted to entries in a sane range so this doesn't produce
    # nonsense like "1 - Avogadro's number".
    for value, entry in rows:
        if not (0 < value < 2):
            continue
        sugg = f"({entry.suggestion})" if _needs_parens(entry.suggestion) else entry.suggestion
        if _agrees(1 - x, value, digits):
            true_value = 1 - value
            return Match(
                form=f"1-({entry.form})",
                suggestion=f"1 - {sugg}",
                note=entry.note,
                tier="table",
                matched_digits=digits,
                surplus=confidence.table_surplus(digits, len(rows)) - confidence.FOLD_PENALTY,
                precision_lost=_precision_lost(x, true_value),
                near_miss=entry.decimal is None and _is_near_miss(x, true_value, digits),
            )
        if _agrees(x + 1, value, digits):
            true_value = value - 1
            return Match(
                form=f"({entry.form})-1",
                suggestion=f"{sugg} - 1",
                note=entry.note,
                tier="table",
                matched_digits=digits,
                surplus=confidence.table_surplus(digits, len(rows)) - confidence.FOLD_PENALTY,
                precision_lost=_precision_lost(x, true_value),
                near_miss=entry.decimal is None and _is_near_miss(x, true_value, digits),
            )
    return None


def _match_rational(x: mpmath.mpf, digits: int) -> Match | None:
    frac = Fraction(float(x)).limit_denominator(MAX_RATIONAL_DENOMINATOR)
    if frac.denominator == 1:
        return None
    true_value = mpmath.mpf(frac.numerator) / frac.denominator
    if not _agrees(x, true_value, digits):
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
        precision_lost=_precision_lost(x, true_value),
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
        lost = _precision_lost(x, value)
    return Match(
        form=found,
        suggestion=_to_python(found),
        note="found by PSLQ search",
        tier="pslq",
        matched_digits=digits,
        surplus=confidence.pslq_surplus(digits, found),
        precision_lost=lost,
    )


def _format_logspace_factor(base: str, exp: Fraction) -> str:
    if exp == 1:
        return base
    if exp.denominator == 1:
        return f"{base}**{exp.numerator}"
    return f"{base}**({exp.numerator}/{exp.denominator})"


def _match_logspace(x: mpmath.mpf, digits: int) -> Match | None:
    """Multiplicative relations like 8/pi or 6/pi**2 - a monomial in a few
    small primes and pi - that the additive PSLQ tier can't express."""
    if digits < LOGSPACE_MIN_DIGITS or x <= 0:
        return None
    with mpmath.workdps(max(digits, 16) + 10):
        try:
            basis = (
                [mpmath.log(x)]
                + [mpmath.log(b) for b in LOGSPACE_BASES]
                + [mpmath.log(mpmath.pi)]
            )
            rel = mpmath.pslq(
                basis, tol=mpmath.mpf(10) ** (2 - digits), maxcoeff=64, maxsteps=2000
            )
        except Exception:
            return None
    if rel is None or rel[0] == 0:
        return None
    c0 = rel[0]
    factors = []
    for base, c in zip((*LOGSPACE_BASES, "pi"), rel[1:]):
        if c != 0:
            factors.append((str(base), Fraction(-c, c0)))
    if not factors:
        return None  # degenerate: x == 1
    if rel[-1] == 0 and all(exp.denominator == 1 for _, exp in factors):
        # no pi factor AND every exponent is an integer: x is an exact
        # rational in disguise (a product of integer prime powers), the
        # rational tier's territory (and it already declined, or we'd not be
        # here). But a zero pi-coefficient does NOT by itself mean x is
        # rational - c0 not dividing an exponent evenly makes x an irrational
        # root of a rational even with no pi involved at all (e.g. x**3 =
        # 7**3/(2*11**4), a cube root, still logspace's job), so that case
        # must fall through instead of bailing here.
        return None
    with mpmath.workdps(digits + 20):
        value = mpmath.mpf(1)
        for base, exp in factors:
            base_value = mpmath.pi if base == "pi" else mpmath.mpf(base)
            value *= base_value ** (mpmath.mpf(exp.numerator) / exp.denominator)
        if not _agrees(x, value, digits):
            return None
        lost = _precision_lost(x, value)
    form = "*".join(_format_logspace_factor(base, exp) for base, exp in factors)
    exponent_cost = sum(
        len(str(abs(exp.numerator))) + len(str(exp.denominator)) for _, exp in factors
    )
    return Match(
        form=form,
        suggestion=_to_python(form),
        note="found by log-space PSLQ search",
        tier="logspace",
        matched_digits=digits,
        surplus=confidence.logspace_surplus(digits, exponent_cost),
        precision_lost=lost,
    )


@lru_cache(maxsize=None)
def recognize(
    text: str,
    min_surplus: float = confidence.DEFAULT_MIN_SURPLUS,
    extra_entries: tuple[ConstantEntry, ...] = (),
) -> Match | None:
    """Try to recognize a float literal (given as source text) as an exact form.

    Results are cached by (text, min_surplus, extra_entries): the same literal
    text appears many times across a real corpus (placeholder values, planted
    test constants), and the PSLQ tiers are expensive. Callers must treat the
    returned Match as immutable - it is shared between identical calls.
    """
    digits = significant_digits(text)
    with mpmath.workdps(max(digits, 15) + 25):
        x = mpmath.mpf(text.replace("_", ""))
        match = _match_table(x, digits, extra_entries)
        if match is not None and match.surplus >= min_surplus:
            return match
        for finder in (_match_rational, _match_pslq, _match_logspace):
            match = finder(x, digits)
            if match is not None and match.surplus >= min_surplus:
                return match
    return None
