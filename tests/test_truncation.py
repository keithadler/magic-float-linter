from exact_linter.recognize import recognize


def test_short_pi_is_truncated():
    match = recognize("3.14159")
    assert match is not None
    assert match.form == "pi"
    assert match.truncated
    assert match.precision_lost >= 8  # ~10 digits lost


def test_eight_digit_pi_is_truncated():
    match = recognize("3.1415927")
    assert match is not None
    assert match.truncated
    assert match.precision_lost >= 6


def test_full_precision_pi_not_truncated():
    match = recognize("3.141592653589793")
    assert match is not None
    assert not match.truncated
    assert match.precision_lost == 0


def test_fifteen_digit_pi_not_truncated():
    # one digit shy of full double precision is still fine
    match = recognize("3.14159265358979")
    assert match is not None
    assert not match.truncated


def test_over_precise_pi_not_truncated():
    # more digits than a double holds: not a truncation
    match = recognize("3.14159265358979323846")
    assert match is not None
    assert not match.truncated


def test_truncated_e():
    match = recognize("2.718281828")
    assert match is not None
    assert match.form == "e"
    assert match.truncated
