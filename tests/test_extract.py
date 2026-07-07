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


def test_list_of_short_tuples_is_nested_data():
    # matplotlib-style colormap table: a list of 3-element RGB triples.
    # Each inner tuple is short (3 < the plain sequence threshold) but the
    # whole thing is clearly a data table, not a handful of constants.
    src = "_Blues_data = [\n    [0.96862745098039216, 0.98431372549019602, 1.0],\n    [0.87058823529411766, 0.92156862745098034, 0.96862745098039216],\n]\n"
    literals = extract_source(src, Path("cm.py"))
    by_text = {lit.text: lit for lit in literals}
    assert by_text["0.96862745098039216"].sequence_size > 3


def test_dict_of_tuples_is_nested_data():
    # named-color-table style: dict mapping name -> RGB tuple
    src = "COLORS = {'aliceblue': (0.941, 0.973, 1.0), 'azure': (0.941, 1.0, 1.0)}\n"
    literals = extract_source(src, Path("colors.py"))
    assert all(lit.sequence_size > 3 for lit in literals)


def test_standalone_short_tuple_is_not_nested_data():
    # a plain coordinate pair, not nested in another container, should be
    # unaffected by the nested-container rule: sequence_size is just the
    # element count (2), nowhere near the nested-data sentinel
    src = "point = (3.14159265358979, 2.71828182845905)\n"
    literals = extract_source(src, Path("s.py"))
    assert all(lit.sequence_size == 2 for lit in literals)
