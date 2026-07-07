"""Whole-array recognition: sequences where every element is an exact
rational or known constant, e.g. a Runge-Kutta weight vector or a run of
reciprocal factorials.

This is currently the tool's biggest blind spot: triage.py skips individual
literals inside a long sequence outright, on the theory that data tables
(measured samples, lookup tables) aren't "magic floats". That's the right
call for a single element in isolation - but a sequence where *every*
element is independently exact, unlike arbitrary measured data, really is
worth surfacing as a unit. The bar is strict on purpose: one unexplained
element sinks the whole sequence, so this never fires on real data tables
that merely contain a few round-looking numbers by chance.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from math import factorial

from .extract import NumericSequence
from .recognize import Match, recognize
from .triage import MAX_DATA_SEQUENCE, MAX_SMALL_INTEGRAL, significant_digits

# only sequences already too long for element-by-element treatment (matches
# the ">MAX_DATA_SEQUENCE" cutoff triage.py uses for the per-element skip)
MIN_SEQUENCE_LENGTH = MAX_DATA_SEQUENCE + 1


@dataclass(frozen=True)
class ElementExplanation:
    text: str
    match: Match | None  # None if trivially self-explanatory (an int, 0, a short/round value)


@dataclass(frozen=True)
class SequenceMatch:
    name: str  # e.g. "classic RK4 weights", or "exact rational/constant sequence"
    suggestion: str  # a Python list literal to replace the whole sequence
    elements: tuple[ElementExplanation, ...]


def _is_trivially_exact(text: str) -> bool:
    """True if this element needs no further explanation: it's already
    exactly what it looks like (an integer, zero, or too short to claim
    anything about). Deliberately does NOT reuse triage.skip_reason - that
    function's "inside a numeric data sequence" rule is exactly the one this
    module exists to supersede for sequences that pass the stricter test below.
    """
    try:
        value = float(text)
    except ValueError:
        return False
    if value == 0:
        return True
    if significant_digits(text) < 6:
        return True
    return abs(value) < MAX_SMALL_INTEGRAL and value == int(value)


def _is_float_text(text: str) -> bool:
    return "." in text or "e" in text.lower()


MIN_NAMED_MATCH_DIGITS = 4  # below this, the tolerance formula below is too loose to mean anything


def _agrees_with_fraction(text: str, target: Fraction) -> bool:
    """True if `text` is a faithful rendering of `target` - either bit-exact
    (always allowed, any digit count: no ambiguity in an exact match), or
    close enough given how many digits `text` actually carries (only once
    there are enough digits for "close enough" to be meaningful evidence
    rather than a coincidence). A short literal like "0.05" carries only one
    significant digit; without the digit-count floor, the relative-tolerance
    formula below would judge it "close enough" to nearly any nearby target
    (caught in the stdlib corpus: an unrelated 5-element list of round
    numbers was wrongly named "reciprocal factorials").
    """
    try:
        value = float(text)
    except ValueError:
        return False
    target_f = float(target)
    if value == target_f:
        return True
    if target_f == 0:
        return False
    digits = significant_digits(text)
    if digits < MIN_NAMED_MATCH_DIGITS:
        return False
    tol = abs(target_f) * 10 ** (1 - digits)
    return abs(value - target_f) <= tol


# a small library of iconic named sequences from numerical methods, as exact
# fractions - checked before falling back to a generic description. Every
# entry must be at least MIN_SEQUENCE_LENGTH long, or it can never match:
# Simpson's classic 1/3 rule (1/3, 4/3, 1/3) is only 3 elements and is
# deliberately omitted for exactly that reason (caught while testing, not
# guessed at - the same "don't ship an unreachable entry" discipline used
# when evaluating and skipping the quadratic minimal-polynomial tier).
#
# Every entry must also be *distinctive*, not just correct: "classic RK4
# nodes" (0, 1/2, 1/2, 1) was here and got removed after the real-world
# corpus scan found it firing on scipy's test_fir_filter_design.py, where
# [0.0, 0.5, 0.5, 1.0] is a normalized frequency band-edge array for an
# FIR filter - nothing to do with Runge-Kutta. The values were correct;
# the *name* was misleading, because a four-point 0/half/half/1 pattern is
# too generic to reliably indicate any one algorithm. RK4 weights
# (1/6, 1/3, 1/3, 1/6) is a much less common pattern and produced zero
# false attributions anywhere in the corpus - kept for that reason.
_NAMED_SEQUENCES: tuple[tuple[str, tuple[Fraction, ...]], ...] = (
    (
        "classic Runge-Kutta (RK4) weights",
        (Fraction(1, 6), Fraction(1, 3), Fraction(1, 3), Fraction(1, 6)),
    ),
    (
        "Simpson's 3/8 rule weights",
        (Fraction(3, 8), Fraction(9, 8), Fraction(9, 8), Fraction(3, 8)),
    ),
)


def _named_match(elements: list[str]) -> str | None:
    for name, fracs in _NAMED_SEQUENCES:
        if len(fracs) == len(elements) and all(
            _agrees_with_fraction(e, f) for e, f in zip(elements, fracs)
        ):
            return name
    n = len(elements)
    if 4 <= n <= 12:
        reciprocal_factorials = tuple(Fraction(1, factorial(k)) for k in range(n))
        if all(_agrees_with_fraction(e, f) for e, f in zip(elements, reciprocal_factorials)):
            return f"reciprocal factorials (1/0! .. 1/{n - 1}!)"
    return None


def identify_sequence(seq: NumericSequence, min_surplus: float) -> SequenceMatch | None:
    """Recognize a whole sequence if every element is exact, or None."""
    if len(seq.elements) < MIN_SEQUENCE_LENGTH:
        return None
    if not any(_is_float_text(e) for e in seq.elements):
        return None  # an all-integer sequence has nothing "magic" to explain
    explanations: list[ElementExplanation] = []
    for text in seq.elements:
        if _is_trivially_exact(text):
            explanations.append(ElementExplanation(text, None))
            continue
        match = recognize(text, min_surplus=min_surplus)
        if match is None:
            return None  # one unexplained element sinks the whole sequence
        explanations.append(ElementExplanation(text, match))

    name = _named_match(seq.elements)
    if name is None:
        # no library match: only worth reporting if something was actually
        # revealed. An unnamed sequence where every element was already
        # trivial (round numbers, short values) has nothing "magic" in it -
        # reporting it would just be noise ("this array of round numbers is
        # exact"... obviously).
        if not any(e.match is not None for e in explanations):
            return None
        name = "exact rational/constant sequence"
    suggestion = "[" + ", ".join(e.match.suggestion if e.match else e.text for e in explanations) + "]"
    return SequenceMatch(name=name, suggestion=suggestion, elements=tuple(explanations))
