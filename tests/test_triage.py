from pathlib import Path

from exact_linter.extract import FloatLiteral
from exact_linter.triage import significant_digits, skip_reason


def lit(text: str, **kwargs) -> FloatLiteral:
    return FloatLiteral(text=text, file=Path("x.py"), line=1, col=0, **kwargs)


def test_significant_digits():
    assert significant_digits("3.141592653589793") == 16
    assert significant_digits("0.001") == 1
    assert significant_digits("1e-6") == 1
    assert significant_digits("6.02214076e23") == 9
    assert significant_digits("0.500000") == 6
    assert significant_digits("1_000.25") == 6
    assert significant_digits("-0.017453292519943295") == 17


def test_skips_boring_literals():
    assert skip_reason(lit("0.5")) is not None
    assert skip_reason(lit("2.0")) is not None
    assert skip_reason(lit("1e-6")) is not None
    assert skip_reason(lit("0.0")) == "zero"
    assert skip_reason(lit("1e400")) == "non-finite"
    assert skip_reason(lit("100000.0")) == "small integral value"
    assert skip_reason(lit("0.123456789", sequence_size=6)) == "inside a numeric data sequence"


def test_keeps_candidates():
    assert skip_reason(lit("3.14159265")) is None
    assert skip_reason(lit("6.02214076e23")) is None
    assert skip_reason(lit("0.017453292519943295")) is None
    assert skip_reason(lit("0.123456789", sequence_size=2)) is None
