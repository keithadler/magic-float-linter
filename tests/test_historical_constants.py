from exact_linter.recognize import recognize


def test_codata_2010_gas_constant_recognized_as_historical():
    m = recognize("8.3144621")
    assert m is not None
    assert m.form == "gas constant R (CODATA 2010)"
    assert "superseded" in m.note
    assert "8.31446261815324" in m.note


def test_historical_constant_not_flagged_truncated():
    # it IS the exact CODATA-2010 value, not a short/wrong rendering of the
    # current one - flagging it truncated or near-miss would misrepresent a
    # deliberate historical value as a bug
    m = recognize("8.3144621")
    assert m.truncated is False
    assert m.near_miss is False
    assert m.precision_lost == 0


def test_current_codata_value_still_matches_plainly():
    # the current-era value must still resolve to the ordinary (non-historical)
    # table entry, not get shadowed by the historical one
    m = recognize("8.31446261815324")
    assert m is not None
    assert m.form == "gas constant R"
    assert "superseded" not in m.note


def test_all_six_historical_entries_resolve():
    cases = {
        "8.854187817e-12": "vacuum permittivity (CODATA 2010/2014)",
        "8.3144621": "gas constant R (CODATA 2010)",
        "5.2917721092e-11": "Bohr radius (CODATA 2010)",
        "7.2973525698e-3": "fine-structure constant (CODATA 2010)",
        "5.670373e-8": "Stefan-Boltzmann sigma (CODATA 2010)",
        "2.8977721e-3": "Wien displacement constant (CODATA 2010)",
    }
    for text, expected_form in cases.items():
        m = recognize(text)
        assert m is not None, text
        assert m.form == expected_form, text
        assert m.truncated is False, text
        assert m.near_miss is False, text


def test_closest_match_wins_not_first_in_table_order():
    # the historical and current gas-constant entries both fall within each
    # other's matching tolerance at 8 digits; the literal must resolve to
    # whichever it actually equals (the historical one here), not whichever
    # happens to be listed first in the table
    m = recognize("8.3144621")
    assert m.form == "gas constant R (CODATA 2010)"
    m2 = recognize("8.31446261815324")
    assert m2.form == "gas constant R"
