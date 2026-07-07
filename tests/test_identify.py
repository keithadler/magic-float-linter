import json

from exact_linter.cli import main


def test_identify_recognized_constant(capsys):
    code = main(["identify", "0.2068966"])
    out = capsys.readouterr().out
    assert code == 0
    assert "6/29" in out
    assert "truncated" in out
    assert "suggestion: 6 / 29" in out


def test_identify_full_precision(capsys):
    code = main(["identify", "3.141592653589793"])
    out = capsys.readouterr().out
    assert code == 0
    assert "= pi" in out
    assert "truncated" not in out


def test_identify_near_miss(capsys):
    code = main(["identify", "2.71827"])
    out = capsys.readouterr().out
    assert code == 0
    assert "LIKELY TYPO" in out
    assert "suggestion: math.e" in out


def test_identify_no_match(capsys):
    code = main(["identify", "0.8315463215476912"])
    out = capsys.readouterr().out
    assert code == 1
    assert "no confident match" in out


def test_identify_negative_number(capsys):
    code = main(["identify", "-3.141592653589793"])
    out = capsys.readouterr().out
    assert code == 0
    assert "pi" in out


def test_identify_not_a_number(capsys):
    code = main(["identify", "banana"])
    err = capsys.readouterr().err
    assert code == 2
    assert "not a number" in err


def test_identify_json(capsys):
    code = main(["identify", "0.017453292519943295", "--json"])
    data = json.loads(capsys.readouterr().out)
    assert code == 0
    assert data["form"] == "pi/180"
    assert data["suggestion"] == "math.pi / 180"


def test_identify_json_no_match(capsys):
    code = main(["identify", "0.8315463215476912", "--json"])
    data = json.loads(capsys.readouterr().out)
    assert code == 1
    assert data is None


def test_identify_respects_min_surplus():
    # astropy's neutrino-correction literal: a real relation (surplus -2.0)
    # that the default gate declines but a lowered one accepts
    value = "0.22710731766"
    assert main(["identify", value]) == 1
    assert main(["identify", value, "--min-surplus", "-3"]) == 0


def test_identify_still_scans_paths_normally(tmp_path, capsys):
    # make sure adding the "identify" dispatch didn't break normal scanning
    (tmp_path / "p.py").write_text("K = 1.4426950408889634\n")
    code = main([str(tmp_path)])
    assert code == 1
    assert "1/ln(2)" in capsys.readouterr().out
