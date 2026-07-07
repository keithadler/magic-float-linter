from exact_linter.recognize import recognize


def test_pi_full_precision():
    match = recognize("3.141592653589793")
    assert match is not None
    assert match.form == "pi"
    assert match.suggestion == "math.pi"
    assert match.tier == "table"


def test_pi_reduced_precision():
    match = recognize("3.14159265")
    assert match is not None
    assert match.form == "pi"


def test_degrees_to_radians():
    match = recognize("0.017453292519943295")
    assert match is not None
    assert match.form == "pi/180"


def test_radians_to_degrees():
    match = recognize("57.29577951308232")
    assert match is not None
    assert match.form == "180/pi"


def test_inverse_ln2():
    match = recognize("1.4426950408889634")
    assert match is not None
    assert match.form == "1/ln(2)"


def test_gaussian_normalization():
    match = recognize("0.3989422804014327")
    assert match is not None
    assert match.form == "1/sqrt(2*pi)"


def test_avogadro():
    match = recognize("6.02214076e23")
    assert match is not None
    assert "N_A" in match.suggestion


def test_repeating_rational():
    match = recognize("0.6666666666666666")
    assert match is not None
    assert match.tier == "rational"
    assert match.form == "2/3"


def test_one_seventh():
    match = recognize("0.14285714285714285")
    assert match is not None
    assert match.form == "1/7"


def test_terminating_rational_ignored():
    # 0.125 is exactly representable; almost always intentional
    assert recognize("0.1250000000") is None


def test_junk_not_flagged():
    for junk in ("0.8315463215476912", "1.2345678901234567", "0.7182563412021456"):
        assert recognize(junk) is None, junk


def test_long_typed_pi_beyond_double():
    match = recognize("3.14159265358979323846264338327950288")
    assert match is not None
    assert match.form == "pi"
