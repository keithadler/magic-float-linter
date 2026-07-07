import json

from exact_linter.cli import main

RK4 = (
    "WEIGHTS = [0.16666666666666666, 0.3333333333333333,"
    " 0.3333333333333333, 0.16666666666666666]\n"
)


def test_sequence_reported_in_text(tmp_path, capsys):
    (tmp_path / "m.py").write_text(RK4)
    code = main([str(tmp_path), "--exit-zero"])
    out = capsys.readouterr().out
    assert code == 0
    assert "classic Runge-Kutta (RK4) weights" in out
    assert "informational - not counted toward pass/fail" in out


def test_sequence_does_not_affect_exit_code(tmp_path, capsys):
    # a sequence-only file (no ordinary findings) must exit 0 even without
    # --exit-zero: sequence findings are informational by design
    (tmp_path / "m.py").write_text(RK4)
    code = main([str(tmp_path)])
    assert code == 0


def test_no_sequences_flag_suppresses(tmp_path, capsys):
    (tmp_path / "m.py").write_text(RK4)
    main([str(tmp_path), "--exit-zero", "--no-sequences"])
    out = capsys.readouterr().out
    assert "Runge-Kutta" not in out
    assert "exact sequence" not in out


def test_sequence_in_json(tmp_path, capsys):
    (tmp_path / "m.py").write_text(RK4)
    main([str(tmp_path), "--exit-zero", "--json"])
    data = json.loads(capsys.readouterr().out)
    assert data["findings"] == []
    assert len(data["sequences"]) == 1
    assert data["sequences"][0]["name"] == "classic Runge-Kutta (RK4) weights"
    assert data["sequences"][0]["suggestion"] == "[1 / 6, 1 / 3, 1 / 3, 1 / 6]"


def test_sequence_in_github_format(tmp_path, capsys):
    (tmp_path / "m.py").write_text(RK4)
    main([str(tmp_path), "--exit-zero", "--format", "github"])
    out = capsys.readouterr().out
    assert "::notice" in out
    assert "classic Runge-Kutta (RK4) weights" in out


def test_sequence_in_sarif_format(tmp_path, capsys):
    (tmp_path / "m.py").write_text(RK4)
    main([str(tmp_path), "--exit-zero", "--format", "sarif"])
    doc = json.loads(capsys.readouterr().out)
    results = doc["runs"][0]["results"]
    assert len(results) == 1
    assert results[0]["ruleId"] == "recognized-sequence"


def test_sequence_and_ordinary_finding_together(tmp_path, capsys):
    (tmp_path / "m.py").write_text(RK4 + "PI = 3.141592653589793\n")
    code = main([str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 1  # the ordinary finding (pi) still drives the exit code
    assert "Runge-Kutta" in out
    assert "1 recognized constant" in out


def test_sequence_suppressed_under_truncation_only(tmp_path, capsys):
    (tmp_path / "m.py").write_text(RK4)
    main([str(tmp_path), "--exit-zero", "--truncation-only"])
    out = capsys.readouterr().out
    assert "Runge-Kutta" not in out


def test_sequence_respects_changed_only(tmp_path, capsys):
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    (tmp_path / "m.py").write_text("x = 1\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)

    (tmp_path / "m.py").write_text("x = 1\n" + RK4)
    code = main([str(tmp_path), "--exit-zero", "--changed-only"])
    out = capsys.readouterr().out
    assert code == 0
    assert "Runge-Kutta" in out


def test_sequences_jobs_parallel_matches_serial(tmp_path, capsys):
    for i in range(4):
        (tmp_path / f"m{i}.py").write_text(RK4)
    main([str(tmp_path), "--exit-zero", "--json"])
    serial = json.loads(capsys.readouterr().out)
    main([str(tmp_path), "--exit-zero", "--json", "--jobs", "2"])
    parallel = json.loads(capsys.readouterr().out)
    assert len(serial["sequences"]) == len(parallel["sequences"]) == 4
