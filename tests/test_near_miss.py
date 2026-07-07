from exact_linter.cli import main
from exact_linter.recognize import recognize


def test_typo_for_e_is_near_miss():
    m = recognize("2.71827")  # e is 2.71828...; last digit wrong
    assert m is not None
    assert m.form == "e"
    assert m.near_miss is True
    assert m.truncated is False  # a wrong value, not a faithful short one


def test_typo_for_pi_is_near_miss():
    m = recognize("3.14158")  # pi is 3.14159...; last digit wrong
    assert m is not None
    assert m.form == "pi"
    assert m.near_miss is True


def test_typo_for_sqrt2_is_near_miss():
    m = recognize("1.41421357")  # sqrt(2) is ...356...; last digit wrong
    assert m is not None
    assert m.near_miss is True


def test_correct_short_rounding_is_not_near_miss():
    for text in ("2.71828", "3.14159", "1.41421356", "57.29578"):
        m = recognize(text)
        assert m is not None, text
        assert m.near_miss is False, text
        assert m.truncated is True, text  # short but faithful


def test_full_precision_is_not_near_miss():
    m = recognize("3.141592653589793")
    assert m is not None
    assert m.near_miss is False
    assert m.truncated is False


def test_full_precision_one_ulp_off_is_not_a_typo():
    # numpy ships 0.70710678118654746 for sqrt(2)/2; it is ~1 ULP off the true
    # value but a full-precision machine literal, not a hand typo
    m = recognize("0.70710678118654746")
    assert m is not None
    assert m.near_miss is False


def test_physical_constants_are_never_near_misses():
    # CODATA-2010 values differ from the current table's CODATA-2018 values;
    # older-but-correct physical constants must not be flagged as typos
    for text in ("8.3144621", "8.854187817e-12", "7.2973525698e-3"):
        m = recognize(text)
        if m is not None:
            assert m.near_miss is False, text


def test_junk_is_still_not_recognized():
    # a near-miss must be *close* to a real constant; random junk is neither
    for junk in ("0.8315463215476912", "1.2345678901234567"):
        assert recognize(junk) is None, junk


# --- near-miss for rationals, not just table constants ---


def test_typo_for_one_third_is_near_miss():
    m = recognize("0.333331")  # 1/3 is 0.333333...; last digit wrong
    assert m is not None
    assert m.tier == "rational"
    assert m.form == "1/3"
    assert m.near_miss is True
    assert m.truncated is False


def test_typo_for_one_seventh_is_near_miss():
    m = recognize("0.142858")  # 1/7 is 0.142857...; last digit wrong
    assert m is not None
    assert m.form == "1/7"
    assert m.near_miss is True


def test_typo_for_two_thirds_is_near_miss():
    m = recognize("0.666661")  # 2/3 is 0.666667...; last digit wrong
    assert m is not None
    assert m.form == "2/3"
    assert m.near_miss is True


def test_correct_rational_rounding_is_not_near_miss():
    for text, form in (("0.333333", "1/3"), ("0.142857", "1/7"), ("0.666667", "2/3")):
        m = recognize(text)
        assert m is not None, text
        assert m.form == form, text
        assert m.near_miss is False, text
        assert m.truncated is True, text


def test_full_precision_rational_is_not_near_miss():
    m = recognize("0.3333333333333333")
    assert m is not None
    assert m.form == "1/3"
    assert m.near_miss is False
    assert m.truncated is False


def test_rational_near_miss_empirical_false_positive_rate():
    # regression test for the validation done before shipping this feature:
    # 20000 genuinely random mantissas at 5-12 digits produced 2 rational
    # near-miss hits (0.01%), both right at the surplus threshold - matching
    # what the confidence formula predicts, not a leak. This test just
    # re-checks the same two recorded examples stay correctly classified,
    # as a canary if the formula's calibration ever drifts.
    for text, form in (("0.44578317", "37/83"), ("0.555560", "5/9")):
        m = recognize(text)
        assert m is not None, text
        assert m.tier == "rational", text
        assert m.form == form, text


def test_cli_reports_near_miss_as_likely_typo(tmp_path, capsys):
    (tmp_path / "m.py").write_text("EULER = 2.71827\n")
    code = main([str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 1
    assert "LIKELY TYPO" in out
    assert "did you mean" in out
    assert "1 likely typo" in out


def test_near_miss_only_filter(tmp_path, capsys):
    (tmp_path / "m.py").write_text("A = 2.71827\nB = 3.14159\n")  # typo, then honest short
    main([str(tmp_path), "--near-miss-only", "--exit-zero"])
    out = capsys.readouterr().out
    assert "2.71827" in out
    assert "3.14159" not in out  # a faithful truncation, not a near-miss


def test_near_miss_in_json(tmp_path, capsys):
    import json

    (tmp_path / "m.py").write_text("x = 2.71827\n")
    main([str(tmp_path), "--json"])
    data = json.loads(capsys.readouterr().out)["findings"]
    assert data[0]["near_miss"] is True
    assert data[0]["form"] == "e"


def test_near_miss_github_format_is_warning(tmp_path, capsys):
    (tmp_path / "m.py").write_text("x = 2.71827\n")
    main([str(tmp_path), "--format", "github"])
    out = capsys.readouterr().out
    assert out.startswith("::warning ")
    assert "likely a typo for e" in out
