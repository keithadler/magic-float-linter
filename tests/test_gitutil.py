import subprocess

import pytest

from exact_linter.gitutil import ALL_LINES, changed_lines, line_is_changed


def _git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path):
    _git("init", "-q", cwd=tmp_path)
    _git("config", "user.email", "t@example.com", cwd=tmp_path)
    _git("config", "user.name", "T", cwd=tmp_path)
    (tmp_path / "a.py").write_text("x = 1\ny = 2\nz = 3\n")
    _git("add", "a.py", cwd=tmp_path)
    _git("commit", "-q", "-m", "initial", cwd=tmp_path)
    return tmp_path


def test_no_changes_yields_no_entries(repo):
    changed = changed_lines(None, repo)
    assert changed is not None
    assert not line_is_changed(changed, repo / "a.py", 1)


def test_uncommitted_edit_is_changed(repo):
    (repo / "a.py").write_text("x = 1\ny = 200\nz = 3\n")
    changed = changed_lines(None, repo)
    assert line_is_changed(changed, repo / "a.py", 2)
    assert not line_is_changed(changed, repo / "a.py", 1)
    assert not line_is_changed(changed, repo / "a.py", 3)


def test_staged_edit_is_changed(repo):
    (repo / "a.py").write_text("x = 1\ny = 200\nz = 3\n")
    _git("add", "a.py", cwd=repo)
    changed = changed_lines(None, repo)
    assert line_is_changed(changed, repo / "a.py", 2)


def test_untracked_new_file_is_all_changed(repo):
    (repo / "b.py").write_text("q = 1\n")
    changed = changed_lines(None, repo)
    assert changed[(repo / "b.py").resolve()] is ALL_LINES
    assert line_is_changed(changed, repo / "b.py", 1)
    assert line_is_changed(changed, repo / "b.py", 999)  # ALL_LINES: any line counts


def test_since_ref_diffs_against_older_commit(repo):
    _git("branch", "-q", "base", cwd=repo)
    (repo / "a.py").write_text("x = 1\ny = 200\nz = 3\n")
    _git("add", "a.py", cwd=repo)
    _git("commit", "-q", "-m", "second", cwd=repo)
    changed = changed_lines("base", repo)
    assert line_is_changed(changed, repo / "a.py", 2)


def test_unrelated_file_not_in_map(repo):
    (repo / "a.py").write_text("x = 1\ny = 200\nz = 3\n")
    changed = changed_lines(None, repo)
    assert not line_is_changed(changed, repo / "does_not_exist.py", 1)


def test_not_a_git_repo_returns_none(tmp_path):
    assert changed_lines(None, tmp_path) is None
