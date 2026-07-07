import json

from exact_linter.cli import main, resolve_allowed_codes
from exact_linter.recognize import recognize

FULL_PI = "3.141592653589793"
SHORT_PI = "3.14159"
TYPO_E = "2.71827"
RK4_WEIGHTS = (
    "WEIGHTS = [0.16666666666666666, 0.3333333333333333,"
    " 0.3333333333333333, 0.16666666666666666]\n"
)


# --- Match.code / SequenceMatch.code ---


def test_recognized_code():
    assert recognize(FULL_PI).code == "recognized"


def test_truncated_code():
    assert recognize(SHORT_PI).code == "truncated"


def test_near_miss_code():
    assert recognize(TYPO_E).code == "near-miss"


# --- resolve_allowed_codes (unit) ---


def test_resolve_no_filters_allows_everything():
    allowed, err = resolve_allowed_codes((), (), False, False)
    assert allowed is None
    assert err is None


def test_resolve_select_restricts():
    allowed, err = resolve_allowed_codes(("truncated",), (), False, False)
    assert allowed == frozenset({"truncated"})
    assert err is None


def test_resolve_ignore_removes_from_everything():
    allowed, err = resolve_allowed_codes((), ("near-miss",), False, False)
    assert allowed == frozenset({"recognized", "truncated", "sequence"})


def test_resolve_select_then_ignore_composes():
    allowed, _ = resolve_allowed_codes(
        ("truncated", "near-miss"), ("near-miss",), False, False
    )
    assert allowed == frozenset({"truncated"})


def test_resolve_truncation_only_shortcut():
    allowed, _ = resolve_allowed_codes((), (), True, False)
    assert allowed == frozenset({"truncated"})


def test_resolve_both_shortcuts_union():
    allowed, _ = resolve_allowed_codes((), (), True, True)
    assert allowed == frozenset({"truncated", "near-miss"})


def test_resolve_select_overrides_shortcuts():
    allowed, _ = resolve_allowed_codes(("recognized",), (), True, True)
    assert allowed == frozenset({"recognized"})


def test_resolve_unknown_code_errors():
    allowed, err = resolve_allowed_codes(("bogus",), (), False, False)
    assert allowed is None
    assert "bogus" in err
    assert "recognized" in err  # lists valid choices


# --- CLI integration ---


def test_cli_select_truncated_only(tmp_path, capsys):
    (tmp_path / "m.py").write_text(f"FULL = {FULL_PI}\nSHORT = {SHORT_PI}\n")
    main([str(tmp_path), "--exit-zero", "--select", "truncated"])
    out = capsys.readouterr().out
    assert "SHORT" in out
    assert "FULL" not in out


def test_cli_ignore_near_miss(tmp_path, capsys):
    (tmp_path / "m.py").write_text(f"FULL = {FULL_PI}\nTYPO = {TYPO_E}\n")
    main([str(tmp_path), "--exit-zero", "--ignore", "near-miss"])
    out = capsys.readouterr().out
    assert "FULL" in out
    assert "TYPO" not in out


def test_cli_select_sequence_only(tmp_path, capsys):
    (tmp_path / "m.py").write_text(f"FULL = {FULL_PI}\n{RK4_WEIGHTS}")
    main([str(tmp_path), "--exit-zero", "--select", "sequence"])
    out = capsys.readouterr().out
    assert "FULL" not in out
    assert "Runge-Kutta" in out


def test_cli_ignore_sequence_equivalent_to_no_sequences(tmp_path, capsys):
    (tmp_path / "m.py").write_text(RK4_WEIGHTS)
    main([str(tmp_path), "--exit-zero", "--ignore", "sequence"])
    assert "Runge-Kutta" not in capsys.readouterr().out


def test_cli_unknown_select_code_errors(tmp_path, capsys):
    (tmp_path / "m.py").write_text(f"FULL = {FULL_PI}\n")
    code = main([str(tmp_path), "--select", "bogus"])
    assert code == 2
    assert "bogus" in capsys.readouterr().err


def test_cli_select_and_truncation_only_together_select_wins(tmp_path, capsys):
    # --select is documented to take precedence over the shortcut flags
    (tmp_path / "m.py").write_text(f"FULL = {FULL_PI}\nSHORT = {SHORT_PI}\n")
    main([str(tmp_path), "--exit-zero", "--select", "recognized", "--truncation-only"])
    out = capsys.readouterr().out
    assert "FULL" in out
    assert "SHORT" not in out


def test_per_line_suppression_is_code_specific(tmp_path, capsys):
    (tmp_path / "m.py").write_text(f"X = {SHORT_PI}  # exact: ignore[near-miss]\n")
    main([str(tmp_path), "--exit-zero"])
    out = capsys.readouterr().out
    # ignore[near-miss] must not suppress a TRUNCATED finding
    assert "TRUNCATED" in out


def test_per_line_suppression_matches_its_own_code(tmp_path, capsys):
    (tmp_path / "m.py").write_text(f"X = {SHORT_PI}  # exact: ignore[truncated]\n")
    main([str(tmp_path), "--exit-zero", "-v"])
    out = capsys.readouterr().out
    assert "TRUNCATED" not in out
    assert "0 recognized constants" in out


def test_select_codes_in_json(tmp_path, capsys):
    (tmp_path / "m.py").write_text(f"FULL = {FULL_PI}\n")
    main([str(tmp_path / "m.py"), "--exit-zero", "--json"])
    data = json.loads(capsys.readouterr().out)
    assert data["findings"][0]["code"] == "recognized"
