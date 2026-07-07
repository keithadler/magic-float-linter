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
    # 3/2 has no pi factor and every exponent is an integer (2*3**-1*... with
    # denominator 1) - x really is a plain rational, the rational tier's call
    match = recognize("1.500000000000")
    assert match is None or match.tier != "logspace"


def test_logspace_no_pi_but_irrational_root_is_not_rejected():
    # a relation with no pi term is NOT automatically "plain rational in
    # disguise": if the PSLQ coefficient on x doesn't evenly divide the other
    # exponents, x is an irrational root of a rational (here, a cube root),
    # which the rational tier could never find. Regression test for a real
    # bug: the original code bailed out whenever the pi-coefficient was zero,
    # regardless of whether the result was actually rational.
    # x**3 == 7**3 / (2 * 11**4), i.e. x == 2**(-1/3) * 7 * 11**(-4/3)
    import mpmath

    with mpmath.workdps(40):
        x = (mpmath.mpf(7) ** 3 / (2 * mpmath.mpf(11) ** 4)) ** (mpmath.mpf(1) / 3)
        text = mpmath.nstr(x, 17, strip_zeros=False)
    match = recognize(text)
    assert match is not None
    assert match.tier == "logspace"
    assert match.form == "2**(-1/3)*7*11**(-4/3)"


def test_logspace_astropy_neutrino_correction_found_but_underevidenced():
    # 7/8 * (4/11)**(4/3), the LambdaCDM neutrino energy-density correction
    # found undetected in astropy's cosmology module during the corpus study.
    # The widened basis {2,3,5,7,11} plus the "no pi" bugfix above now let
    # PSLQ find the relation (2**(-1/3) * 7 * 11**(-4/3)) even for this
    # literal - but astropy only wrote 11 significant digits, and honestly
    # supporting a 3-factor relation with a denominator-3 exponent needs more
    # evidence than that. The default confidence gate correctly declines it
    # (surplus -2.0); a user auditing marginal cases can still recover it by
    # lowering --min-surplus. This is the gate working as designed, not a
    # remaining gap in the search.
    assert recognize("0.22710731766") is None
    found = recognize("0.22710731766", min_surplus=-3.0)
    assert found is not None
    assert found.tier == "logspace"
    assert found.form == "2**(-1/3)*7*11**(-4/3)"
