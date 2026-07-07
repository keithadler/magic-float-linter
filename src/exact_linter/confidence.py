"""Evidence scoring: do the matched digits justify the complexity of the claim?

The core idea: a literal with d significant digits provides roughly d digits
of evidence. A claimed match "costs" the digits needed to describe it plus
the (log10) size of the space that was searched to find it. The surplus is
evidence minus cost; findings below the surplus threshold are suppressed as
likely coincidences.
"""

from __future__ import annotations

import re

DEFAULT_MIN_SURPLUS = 2.0

# effective log10 of the number of candidate expressions each tier searches
TABLE_SEARCH_DIGITS = 2.1  # a curated table of ~100 entries
PSLQ_SEARCH_DIGITS = 6.0  # coefficient combinations over the constant basis


def integer_digit_cost(expr: str) -> int:
    return sum(len(group) for group in re.findall(r"\d+", expr))


def table_surplus(digits: int) -> float:
    # table entries are enumerated, so their internal complexity is already
    # paid for by the table-size term
    return digits - TABLE_SEARCH_DIGITS


def rational_surplus(digits: int, numerator: int, denominator: int) -> float:
    # a random d-digit mantissa lies within 10^-d of some p/q with q <= Q
    # with probability ~ Q^2 * 10^-d, so the denominator is charged twice
    return digits - len(str(abs(numerator))) - 2 * len(str(denominator))


def pslq_surplus(digits: int, expr: str) -> float:
    names = len(re.findall(r"[a-zA-Z_]+", expr))
    return digits - integer_digit_cost(expr) - names - PSLQ_SEARCH_DIGITS
