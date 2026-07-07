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


def test_logspace_fractional_root_over_pi():
    # 2**(1/3) / pi - a fractional exponent, not expressible by the additive
    # PSLQ tier's basis and not already covered by table/reciprocal folding
    match = recognize("0.40104532599259912")
    assert match is not None
    assert match.tier == "logspace"
    assert match.form == "2**(1/3)*pi**-1"
    assert match.suggestion == "2**(1/3)*math.pi**-1"


def test_logspace_two_bases_with_fractional_exponent():
    match = recognize("0.49396778800781745")
    assert match is not None
    assert match.tier == "logspace"
    assert match.form == "3**(2/5)*pi**-1"
    assert match.suggestion == "3**(2/5)*math.pi**-1"


def test_logspace_rejects_pure_rational():
    # 3/2 has no pi factor - that's the rational tier's call, not logspace's
    match = recognize("1.500000000000")
    assert match is None or match.tier != "logspace"


def test_logspace_known_miss_needs_wider_prime_basis():
    # 7/8 * (4/11)**(4/3), the ACDM neutrino energy-density correction found
    # (undetected) in astropy's cosmology module during the corpus study.
    # Needs primes 7 and 11, outside our basis of {2, 3, 5, pi} - documenting
    # this as a known, deliberate limitation rather than silently missing it.
    assert recognize("0.22710731766") is None
