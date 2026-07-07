"""Decide which float literals are worth trying to recognize.

Most floats in real code are boring (0.5, tolerances, table data). Skipping
them aggressively is what keeps the false-positive rate near zero: a literal
only reaches the recognition engine when it carries enough digits to serve
as evidence for a claim.
"""

from __future__ import annotations

import math

from .extract import FloatLiteral

MIN_DIGITS = 6
MAX_SMALL_INTEGRAL = 1_000_000
MAX_DATA_SEQUENCE = 3  # literals in numeric sequences longer than this are treated as data


def significant_digits(text: str) -> int:
    t = text.lower().replace("_", "").lstrip("+-")
    mantissa = t.split("e", 1)[0].replace(".", "").lstrip("0")
    return len(mantissa)


def skip_reason(lit: FloatLiteral, min_digits: int = MIN_DIGITS) -> str | None:
    """Return why this literal should be skipped, or None if it is a candidate."""
    try:
        value = float(lit.text)
    except ValueError:
        return "unparseable"
    if math.isnan(value) or math.isinf(value):
        return "non-finite"
    if value == 0:
        return "zero"
    if significant_digits(lit.text) < min_digits:
        return f"fewer than {min_digits} significant digits"
    if abs(value) < MAX_SMALL_INTEGRAL and value == int(value):
        return "small integral value"
    if lit.sequence_size > MAX_DATA_SEQUENCE:
        return "inside a numeric data sequence"
    return None
