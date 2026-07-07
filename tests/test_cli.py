import json

from exact_linter.cli import iter_python_files, main


def test_cli_finds_planted_constant(tmp_path, capsys):
    (tmp_path / "planted.py").write_text(
        "RAD_PER_DEG = 0.017453292519943295\nJUNK = 0.8315463215476912\n"
    )
    code = main([str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 1
    assert "pi/180" in out
    assert "0.8315463215476912" not in out


def test_cli_clean_file_exits_zero(tmp_path, capsys):
    (tmp_path / "clean.py").write_text("x = 1\ny = 0.5\n")
    assert main([str(tmp_path)]) == 0
    assert "0 recognized constants" in capsys.readouterr().out


def test_cli_exit_zero_flag(tmp_path, capsys):
    (tmp_path / "p.py").write_text("K = 1.4426950408889634\n")
    assert main([str(tmp_path), "--exit-zero"]) == 0


def test_cli_json_output(tmp_path, capsys):
    (tmp_path / "p.py").write_text("K = 1.4426950408889634\n")
    code = main([str(tmp_path / "p.py"), "--json"])
    data = json.loads(capsys.readouterr().out)
    assert code == 1
    assert len(data) == 1
    assert data[0]["form"] == "1/ln(2)"
    assert data[0]["context"] == "K"
    assert data[0]["line"] == 1
    assert data[0]["truncated"] is False
    assert data[0]["precision_lost"] == 0


def test_scans_a_directory_that_lives_inside_site_packages(tmp_path):
    # scanning a package installed under .../site-packages/pkg must still
    # find its files: "site-packages" is an ancestor of the scan root here,
    # not something nested inside it
    pkg_dir = tmp_path / "venv" / "lib" / "site-packages" / "mypkg"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "mod.py").write_text("x = 1\n")
    assert list(iter_python_files([str(pkg_dir)])) == [pkg_dir / "mod.py"]


def test_excludes_nested_venv_within_scanned_tree(tmp_path):
    (tmp_path / "app.py").write_text("x = 1\n")
    nested = tmp_path / ".venv" / "lib" / "site-packages" / "dep"
    nested.mkdir(parents=True)
    (nested / "mod.py").write_text("y = 2\n")
    found = list(iter_python_files([str(tmp_path)]))
    assert found == [tmp_path / "app.py"]


def test_cli_github_format(tmp_path, capsys):
    (tmp_path / "p.py").write_text("SHORT = 3.14159\nFULL = 1.4426950408889634\n")
    code = main([str(tmp_path), "--format", "github"])
    out = capsys.readouterr().out
    assert code == 1
    lines = [line for line in out.splitlines() if line]
    assert len(lines) == 2
    truncated_line = next(line for line in lines if "3.14159" in line)
    assert truncated_line.startswith("::warning file=")
    assert "is pi; suggest math.pi" in truncated_line
    full_line = next(line for line in lines if "1.4426950408889634" in line)
    assert full_line.startswith("::notice file=")


def test_cli_github_format_no_findings(tmp_path, capsys):
    (tmp_path / "p.py").write_text("x = 1\n")
    code = main([str(tmp_path), "--format", "github"])
    assert code == 0
    assert capsys.readouterr().out == ""


def test_cli_json_flag_is_format_json_shortcut(tmp_path, capsys):
    (tmp_path / "p.py").write_text("K = 1.4426950408889634\n")
    out_json = main([str(tmp_path / "p.py"), "--json"])
    data_via_flag = capsys.readouterr().out
    out_format = main([str(tmp_path / "p.py"), "--format", "json"])
    data_via_format = capsys.readouterr().out
    assert out_json == out_format == 1
    assert data_via_flag == data_via_format


def test_cli_suppression_comment(tmp_path, capsys):
    (tmp_path / "p.py").write_text(
        "A = 3.141592653589793  # exact: ignore\nB = 3.141592653589793\n"
    )
    code = main([str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 1
    assert "1 recognized constant" in out


def test_cli_suppression_shows_in_verbose(tmp_path, capsys):
    (tmp_path / "p.py").write_text("A = 3.141592653589793  # exact: ignore\n")
    main([str(tmp_path), "--exit-zero", "-v"])
    out = capsys.readouterr().out
    assert "suppressed by comment" in out


def test_cli_truncation_only(tmp_path, capsys):
    (tmp_path / "p.py").write_text(
        "SHORT = 3.14159\nFULL = 3.141592653589793\n"
    )
    code = main([str(tmp_path), "--truncation-only"])
    out = capsys.readouterr().out
    assert code == 1
    assert "SHORT" in out and "TRUNCATED" in out
    assert "FULL" not in out  # full-precision pi is recognized but not truncated
    assert "1 truncated" in out
