import subprocess

from exact_linter.cli import main


def _git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _init_repo(tmp_path):
    _git("init", "-q", cwd=tmp_path)
    _git("config", "user.email", "t@example.com", cwd=tmp_path)
    _git("config", "user.name", "T", cwd=tmp_path)


def test_changed_only_reports_only_new_finding(tmp_path, capsys):
    _init_repo(tmp_path)
    (tmp_path / "p.py").write_text("OLD = 0.017453292519943295\n")
    _git("add", "p.py", cwd=tmp_path)
    _git("commit", "-q", "-m", "initial", cwd=tmp_path)

    (tmp_path / "p.py").write_text(
        "OLD = 0.017453292519943295\nNEW = 2.718281828459045\n"
    )
    code = main([str(tmp_path), "--changed-only"])
    out = capsys.readouterr().out
    assert code == 1
    assert "2.718281828459045" in out
    assert "0.017453292519943295" not in out  # pre-existing, untouched line


def test_changed_only_new_file_fully_scanned(tmp_path, capsys):
    _init_repo(tmp_path)
    (tmp_path / "a.py").write_text("x = 1\n")
    _git("add", "a.py", cwd=tmp_path)
    _git("commit", "-q", "-m", "initial", cwd=tmp_path)

    (tmp_path / "b.py").write_text("R = 0.017453292519943295\n")  # untracked, new
    code = main([str(tmp_path), "--changed-only"])
    out = capsys.readouterr().out
    assert code == 1
    assert "pi/180" in out


def test_changed_only_clean_diff_reports_nothing(tmp_path, capsys):
    _init_repo(tmp_path)
    (tmp_path / "p.py").write_text("OLD = 0.017453292519943295\n")
    _git("add", "p.py", cwd=tmp_path)
    _git("commit", "-q", "-m", "initial", cwd=tmp_path)

    code = main([str(tmp_path), "--changed-only"])
    out = capsys.readouterr().out
    assert code == 0
    assert "0 recognized constants found" in out


def test_changed_only_outside_git_repo_errors(tmp_path, capsys):
    code = main([str(tmp_path), "--changed-only"])
    err = capsys.readouterr().err
    assert code == 2
    assert "requires a git repository" in err


def test_since_flag_requires_changed_only(tmp_path, capsys):
    code = main([str(tmp_path), "--since", "main"])
    err = capsys.readouterr().err
    assert code == 2
    assert "only applies with --changed-only" in err


def test_since_ref_scopes_to_a_branch_point(tmp_path, capsys):
    _init_repo(tmp_path)
    (tmp_path / "p.py").write_text("OLD = 0.017453292519943295\n")
    _git("add", "p.py", cwd=tmp_path)
    _git("commit", "-q", "-m", "initial", cwd=tmp_path)
    _git("branch", "-q", "base", cwd=tmp_path)

    (tmp_path / "p.py").write_text(
        "OLD = 0.017453292519943295\nNEW = 2.718281828459045\n"
    )
    _git("add", "p.py", cwd=tmp_path)
    _git("commit", "-q", "-m", "second", cwd=tmp_path)

    code = main([str(tmp_path), "--changed-only", "--since", "base"])
    out = capsys.readouterr().out
    assert code == 1
    assert "2.718281828459045" in out
