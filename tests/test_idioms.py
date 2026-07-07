import json
from pathlib import Path

from exact_linter.cli import main
from exact_linter.extract import extract_source
from exact_linter.idioms import idiomatic
from exact_linter.recognize import recognize


def _finding_parts(src: str):
    literal = extract_source(src, Path("s.py"))[0]
    match = recognize(literal.text)
    assert match is not None
    return match, literal


def test_radians_idiom():
    match, literal = _finding_parts("rad = deg * 0.017453292519943295\n")
    assert idiomatic(match, literal) == "math.radians(deg)"


def test_degrees_idiom_via_division():
    match, literal = _finding_parts("deg = rad / 0.017453292519943295\n")
    assert idiomatic(match, literal) == "math.degrees(rad)"


def test_degrees_idiom_via_multiplication():
    match, literal = _finding_parts("deg = rad * 57.29577951308232\n")
    assert idiomatic(match, literal) == "math.degrees(rad)"


def test_tau_idiom():
    match, literal = _finding_parts("circumference = r * 6.283185307179586\n")
    assert idiomatic(match, literal) == "math.tau * r"


def test_no_idiom_without_simple_operand():
    match, literal = _finding_parts("rad = (a + b) * 0.017453292519943295\n")
    assert idiomatic(match, literal) is None


def test_no_idiom_for_bare_assignment():
    match, literal = _finding_parts("RAD_PER_DEG = 0.017453292519943295\n")
    assert idiomatic(match, literal) is None


def test_no_presumptuous_log_idiom():
    # x * (1/ln 2) is log2(e**x), NOT log2(x): no idiom must fire here
    match, literal = _finding_parts("bits = x * 1.4426950408889634\n")
    assert match.form == "1/ln(2)"
    assert idiomatic(match, literal) is None


def test_cli_renders_idiom(tmp_path, capsys):
    (tmp_path / "geo.py").write_text("rad = deg * 0.017453292519943295\n")
    code = main([str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 1
    assert "suggestion: math.radians(deg)" in out
    assert "replaces the whole expression" in out


def test_cli_json_includes_idiom(tmp_path, capsys):
    (tmp_path / "geo.py").write_text("rad = deg * 0.017453292519943295\nPI = 3.141592653589793\n")
    main([str(tmp_path), "--exit-zero", "--json"])
    data = json.loads(capsys.readouterr().out)
    by_literal = {d["literal"]: d for d in data}
    assert by_literal["0.017453292519943295"]["idiomatic"] == "math.radians(deg)"
    assert by_literal["3.141592653589793"]["idiomatic"] is None