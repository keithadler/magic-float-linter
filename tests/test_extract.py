from pathlib import Path

from exact_linter.extract import extract_source

SOURCE = """\
DEG = 57.29577951308232


def f(x, scale=0.017453292519943295):
    data = [1.1, 2.2, 3.3, 4.4, 5.5]
    return x * scale


area = compute(radius=3.141592653589793)
TAU = 6.283185307179586
"""


def test_extract_literals_with_context():
    literals = extract_source(SOURCE, Path("sample.py"))
    by_text = {lit.text: lit for lit in literals}

    assert by_text["57.29577951308232"].context == "DEG"
    assert by_text["57.29577951308232"].line == 1

    assert by_text["0.017453292519943295"].context == "scale"
    assert by_text["3.141592653589793"].context == "radius"
    assert by_text["6.283185307179586"].context == "TAU"

    assert by_text["1.1"].sequence_size == 5
    assert by_text["57.29577951308232"].sequence_size == 0


def test_syntax_error_returns_empty():
    assert extract_source("def broken(:", Path("bad.py")) == []


def test_trailing_comment_suppresses():
    src = "x = 3.141592653589793  # exact: ignore\ny = 2.718281828459045\n"
    literals = extract_source(src, Path("s.py"))
    by_text = {lit.text: lit for lit in literals}
    assert by_text["3.141592653589793"].suppressed is True
    assert by_text["2.718281828459045"].suppressed is False


def test_comment_above_suppresses():
    src = "# exact: ignore\nx = 3.141592653589793\n"
    literals = extract_source(src, Path("s.py"))
    assert literals[0].suppressed is True


def test_comment_above_does_not_leak_to_next_literal():
    src = "# exact: ignore\nx = 3.141592653589793\ny = 2.718281828459045\n"
    literals = extract_source(src, Path("s.py"))
    by_text = {lit.text: lit for lit in literals}
    assert by_text["3.141592653589793"].suppressed is True
    assert by_text["2.718281828459045"].suppressed is False


def test_unrelated_comment_does_not_suppress():
    src = "x = 3.141592653589793  # just a comment\n"
    assert extract_source(src, Path("s.py"))[0].suppressed is False
