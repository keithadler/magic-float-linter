import mpmath

from exact_linter.constants import table
from exact_linter.recognize import recognize


def test_table_builds_and_has_no_duplicate_values():
    rows = table()
    assert len(rows) > 100
    seen: dict[str, str] = {}
    with mpmath.workdps(20):
        for value, entry in rows:
            key = mpmath.nstr(value, 12)
            assert key not in seen, f"{entry.form} duplicates {seen[key]}"
            seen[key] = entry.form


def test_table_values_are_finite_and_positive_precision():
    for value, entry in table():
        assert mpmath.isfinite(value), entry.form
        assert value != 0, entry.form


def test_gelu_coefficient():
    match = recognize("0.7978845608028654")
    assert match is not None
    assert match.form == "sqrt(2/pi)"


def test_stirling_constant():
    match = recognize("0.9189385332046727")
    assert match is not None
    assert match.form == "ln(2*pi)/2"


def test_z_score_1_96():
    match = recognize("1.959963984540054")
    assert match is not None
    assert "0.975" in match.suggestion


def test_mad_consistency_factor():
    match = recognize("1.4826022185056018")
    assert match is not None
    assert "MAD" in match.note


def test_pound_to_kg():
    match = recognize("0.45359237")
    assert match is not None
    assert match.suggestion == "scipy.constants.pound"


def test_arcseconds_per_radian():
    match = recognize("206264.80624709636")
    assert match is not None
    assert match.form == "648000/pi"


def test_inverse_fine_structure():
    match = recognize("137.035999084")
    assert match is not None
    assert "fine_structure" in match.suggestion
