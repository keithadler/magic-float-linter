from exact_linter.recognize import recognize

# CIE Lab (color science)


def test_cie_lab_kappa_full_precision():
    m = recognize("903.2962962962962962962963")
    assert m is not None
    assert m.tier == "table"
    assert m.suggestion == "24389 / 27"


def test_cie_lab_kappa_double_precision():
    # a realistic literal (double can't hold more than ~17 sig figs)
    m = recognize("903.29629629629630")
    assert m is not None
    assert m.suggestion == "24389 / 27"


def test_cie_lab_epsilon():
    m = recognize("0.008856451679035630817171676")
    assert m is not None
    assert m.suggestion == "216 / 24389"
    assert "(6/29)" in m.note


def test_cie_lab_entries_use_full_precision_not_float64_division():
    # regression test: a bare "24389/27" in eval() computes in float64 before
    # mpf() ever wraps it, silently truncating the repeating decimal at
    # double precision instead of computing it at full (60-digit) precision
    # like every other math entry. Only a literal beyond double precision
    # can tell the two apart.
    m = recognize("903.29629629629629629629630")  # correct to 26 digits
    assert m is not None
    assert m.precision_lost == 0


# dB / acoustics


def test_3db_half_power_point():
    m = recognize("3.0102999566398119521")
    assert m is not None
    assert m.suggestion == "10 * math.log10(2)"
    assert "3 dB" in m.note


def test_6db_amplitude_doubling():
    m = recognize("6.0205999132796239043")
    assert m is not None
    assert m.suggestion == "20 * math.log10(2)"


# exact unit conversions (terminating decimals - previously unreachable, since
# the rational tier deliberately declines to report terminating decimals)


def test_acre_recognized_at_default_settings():
    m = recognize("4046.8564224")
    assert m is not None
    assert m.suggestion == "scipy.constants.acre"


def test_inch_foot_yard_not_reachable_at_default_surplus():
    # their exact decimal representation is inherently short (3-4 sig figs -
    # that IS the complete value), so they can never accumulate enough
    # evidence to clear the default confidence gate against the full table.
    # Same honestly-gated situation as the astropy neutrino correction.
    for text in ("0.0254", "0.3048", "0.9144"):
        assert recognize(text) is None, text


def test_inch_foot_yard_recoverable_at_lower_surplus():
    cases = {
        "0.0254": "scipy.constants.inch",
        "0.3048": "scipy.constants.foot",
        "0.9144": "scipy.constants.yard",
    }
    for text, suggestion in cases.items():
        m = recognize(text, min_surplus=-2.0)
        assert m is not None, text
        assert m.suggestion == suggestion, text


def test_terminating_decimal_still_declined_generically():
    # a plain, non-curated terminating decimal must still be declined - only
    # specific, named constants get an explicit table entry
    assert recognize("0.125") is None
