from exact_linter.recognize import recognize


def test_reciprocal_of_unlisted_constant():
    # 1/sqrt(5) is not a table entry, but sqrt(5) is; folding should catch it
    match = recognize("0.4472135954999579")
    assert match is not None
    assert match.form == "1/(sqrt(5))"
    assert match.suggestion == "1 / math.sqrt(5)"


def test_reciprocal_of_physical_constant():
    # 1/c, the light-travel time per metre, in seconds
    match = recognize("3.3356409519815204e-9")
    assert match is not None
    assert match.form == "1/(speed of light c)"
    assert match.suggestion == "1 / scipy.constants.c"


def test_direct_entry_preferred_over_fold():
    # 1/pi is a listed entry; it should match directly, not as a fold
    match = recognize("0.3183098861837907")
    assert match is not None
    assert match.form == "1/pi"  # listed form, not "1/(pi)"


def test_reciprocal_fold_of_sqrt7():
    match = recognize("0.3779644730092272")
    assert match is not None
    assert match.form == "1/(sqrt(7))"


def test_complement_fold_exponential_saturation():
    # 1 - 1/e: exponential saturation / charging-capacitor constant
    match = recognize("0.6321205588285577")
    assert match is not None
    assert match.form == "1-(1/e)"
    assert match.suggestion == "1 - (1 / math.e)"


def test_shift_fold():
    # 1/pi - 1, not itself a table entry but 1/pi shifted down by one
    match = recognize("-0.6816901138162093")
    assert match is not None
    assert match.form == "(1/pi)-1"
    assert match.suggestion == "(1 / math.pi) - 1"


def test_complement_fold_does_not_fire_on_large_constants():
    # 1 - speed of light shouldn't be attempted: entries outside (0, 2) are
    # excluded from complement/shift folding as meaningless
    assert recognize("-299792457.0") is None
