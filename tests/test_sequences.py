from pathlib import Path

from exact_linter.extract import NumericSequence, extract_source_info
from exact_linter.sequences import MIN_SEQUENCE_LENGTH, _NAMED_SEQUENCES, identify_sequence


def _seq(*elements: str) -> NumericSequence:
    return NumericSequence(elements=list(elements), file=Path("x.py"), line=1, col=0)


def test_named_sequences_are_all_reachable():
    # regression test for the Simpson's-1/3 dead-weight bug: every library
    # entry must be at least MIN_SEQUENCE_LENGTH long or it can never match
    for name, fracs in _NAMED_SEQUENCES:
        assert len(fracs) >= MIN_SEQUENCE_LENGTH, name


def test_rk4_weights_recognized():
    seq = _seq(
        "0.16666666666666666",
        "0.3333333333333333",
        "0.3333333333333333",
        "0.16666666666666666",
    )
    m = identify_sequence(seq, min_surplus=2.0)
    assert m is not None
    assert m.name == "classic Runge-Kutta (RK4) weights"
    assert m.suggestion == "[1 / 6, 1 / 3, 1 / 3, 1 / 6]"


def test_rk4_nodes_recognized_even_though_every_element_is_trivial():
    seq = _seq("0.0", "0.5", "0.5", "1.0")
    m = identify_sequence(seq, min_surplus=2.0)
    assert m is not None
    assert m.name == "classic Runge-Kutta (RK4) nodes"


def test_simpson_38_recognized():
    seq = _seq("0.375", "1.125", "1.125", "0.375")
    m = identify_sequence(seq, min_surplus=2.0)
    assert m is not None
    assert m.name == "Simpson's 3/8 rule weights"


def test_factorial_reciprocals_recognized():
    seq = _seq("1.0", "1.0", "0.5", "0.16666666666666666", "0.041666666666666664")
    m = identify_sequence(seq, min_surplus=2.0)
    assert m is not None
    assert m.name == "reciprocal factorials (1/0! .. 1/4!)"
    assert m.suggestion == "[1.0, 1.0, 0.5, 1 / 6, 1 / 24]"


def test_one_unexplained_element_sinks_the_whole_sequence():
    seq = _seq(
        "0.16666666666666666",
        "0.3333333333333333",
        "0.8315463215476912",  # junk, not a known constant
        "0.16666666666666666",
    )
    assert identify_sequence(seq, min_surplus=2.0) is None


def test_unnamed_all_trivial_sequence_is_not_noise():
    # every element is individually trivial (short/round) and the sequence
    # matches no named library entry - nothing was actually revealed, so
    # this must NOT be reported (would just be "these round numbers are
    # exact... obviously")
    seq = _seq("0.5", "1.5", "2.5", "3.5", "4.5")
    assert identify_sequence(seq, min_surplus=2.0) is None


def test_unnamed_sequence_with_a_genuine_reveal_is_reported():
    # not a named library sequence, but one element genuinely needed
    # recognition (pi/180) - that IS worth surfacing
    seq = _seq("0.017453292519943295", "2.0", "3.0", "4.0")
    m = identify_sequence(seq, min_surplus=2.0)
    assert m is not None
    assert m.name == "exact rational/constant sequence"
    assert "math.pi / 180" in m.suggestion


def test_short_digit_literals_do_not_falsely_match_named_sequences():
    # regression test: found via the stdlib corpus scan. [0.05, 0.04, 0.03,
    # 0.02, 0.01] (test_sched.py) was wrongly named "reciprocal factorials"
    # because a 1-significant-digit literal like "0.05" produced an
    # absurdly loose tolerance (+/-1.0) against the relative-tolerance
    # formula, "agreeing" with almost any nearby target.
    seq = _seq("0.05", "0.04", "0.03", "0.02", "0.01")
    assert identify_sequence(seq, min_surplus=2.0) is None


def test_all_integer_sequence_has_nothing_to_explain():
    seq = _seq("1", "4", "6", "4", "1")  # Pascal's-triangle-looking int row
    assert identify_sequence(seq, min_surplus=2.0) is None


def test_too_short_sequence_is_not_considered():
    seq = _seq("0.16666666666666666", "0.3333333333333333", "0.16666666666666666")
    assert len(seq.elements) < MIN_SEQUENCE_LENGTH
    assert identify_sequence(seq, min_surplus=2.0) is None


def test_negative_elements_supported():
    seq = _seq("-0.5", "0.16666666666666666", "0.3333333333333333", "-1.0")
    # trivial(-0.5) + real(pi-ish placeholder) - just confirm sign parses and
    # doesn't crash; use a genuine constant so it's actually reportable
    m = identify_sequence(seq, min_surplus=2.0)
    assert m is not None


# --- extraction ---


def test_extracts_flat_numeric_sequence():
    src = "WEIGHTS = [0.16666666666666666, 0.3333333333333333, 0.3333333333333333, 0.16666666666666666]\n"
    info = extract_source_info(src, Path("s.py"))
    assert len(info.sequences) == 1
    assert info.sequences[0].elements == [
        "0.16666666666666666",
        "0.3333333333333333",
        "0.3333333333333333",
        "0.16666666666666666",
    ]


def test_sequence_with_non_numeric_element_not_captured():
    src = "x = [0.16666666666666666, 0.3333333333333333, name, 0.16666666666666666]\n"
    info = extract_source_info(src, Path("s.py"))
    assert info.sequences == []


def test_nested_container_not_captured_as_a_sequence():
    # a list of RGB-ish triples: a data table, not a coefficient vector
    src = "COLORS = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6], [0.7, 0.8, 0.9], [0.11, 0.22, 0.33]]\n"
    info = extract_source_info(src, Path("s.py"))
    assert info.sequences == []


def test_hex_int_literal_in_sequence_does_not_crash():
    # regression test: found via a real crash scanning numpy's source, which
    # has a float16-bit-pattern lookup table like [0x3c00, 0.5, ...]. Pure
    # int elements are intentionally captured (see test_all_integer_sequence_
    # has_nothing_to_explain), but "0x3c00" is valid Python int syntax that
    # float() cannot parse - passing it through crashed deep inside
    # recognize(), which assumes every string it receives is float-parseable.
    src = "TABLE = [0x3c00, 0.16666666666666666, 0.3333333333333333, 0.5, 0.16666666666666666]\n"
    info = extract_source_info(src, Path("s.py"))
    assert info.sequences == []  # the whole sequence is left uncaptured, not partially


def test_negative_elements_extracted_whole():
    src = "x = [-0.5, 0.16666666666666666, 0.3333333333333333, -1.0]\n"
    info = extract_source_info(src, Path("s.py"))
    assert len(info.sequences) == 1
    assert info.sequences[0].elements[0] == "-0.5"
    assert info.sequences[0].elements[3] == "-1.0"


def test_short_sequence_still_extracted_but_wont_pass_min_length():
    src = "x = [0.16666666666666666, 0.3333333333333333, 0.16666666666666666]\n"
    info = extract_source_info(src, Path("s.py"))
    assert len(info.sequences) == 1
    assert len(info.sequences[0].elements) == 3
