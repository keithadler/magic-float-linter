import subprocess
import sys

from exact_linter.flake8_plugin import ExactChecker


def _run(lines: list[str]) -> list[tuple[int, int, str, type]]:
    checker = ExactChecker(tree=None, filename="m.py", lines=lines)
    return list(checker.run())


def test_recognized():
    results = _run(["FULL = 3.141592653589793\n"])
    assert len(results) == 1
    line, col, message, cls = results[0]
    assert (line, col) == (1, 7)
    assert message.startswith("EXA001")
    assert "math.pi" in message
    assert cls is ExactChecker


def test_truncated():
    (_, _, message, _), = _run(["SHORT = 3.14159\n"])
    assert message.startswith("EXA002")
    assert "accurate to only 6 digits" in message


def test_near_miss():
    (_, _, message, _), = _run(["TYPO = 2.71827\n"])
    assert message.startswith("EXA003")
    assert "typo for e" in message


def test_no_findings_yields_nothing():
    assert _run(["x = 1\ny = 0.5\n"]) == []


def test_bare_suppression_respected():
    assert _run(["x = 3.141592653589793  # exact: ignore\n"]) == []


def test_code_specific_suppression_respected():
    assert _run(["x = 3.14159  # exact: ignore[truncated]\n"]) == []


def test_code_specific_suppression_does_not_leak():
    # ignore[near-miss] must not suppress a truncated finding
    results = _run(["x = 3.14159  # exact: ignore[near-miss]\n"])
    assert len(results) == 1
    assert results[0][2].startswith("EXA002")


def test_reads_from_disk_when_no_lines_given(tmp_path):
    f = tmp_path / "m.py"
    f.write_text("FULL = 3.141592653589793\n")
    checker = ExactChecker(tree=None, filename=str(f), lines=None)
    results = list(checker.run())
    assert len(results) == 1
    assert results[0][2].startswith("EXA001")


def test_config_select_respected(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[tool.exact]\nselect = ["near-miss"]\n')
    f = tmp_path / "m.py"
    f.write_text("FULL = 3.141592653589793\nTYPO = 2.71827\n")
    checker = ExactChecker(tree=None, filename=str(f), lines=None)
    results = list(checker.run())
    assert len(results) == 1
    assert results[0][2].startswith("EXA003")


def test_missing_file_yields_nothing():
    checker = ExactChecker(tree=None, filename="/nonexistent/path/m.py", lines=None)
    assert list(checker.run()) == []


# --- real entry-point discovery, not just direct instantiation ---


def test_flake8_actually_discovers_the_plugin(tmp_path):
    (tmp_path / "m.py").write_text(
        "FULL = 3.141592653589793\nSUPPRESSED = 2.71827  # exact: ignore\n"
    )
    result = subprocess.run(
        [sys.executable, "-m", "flake8", "--select=EXA", "m.py"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert "EXA001" in result.stdout
    assert result.returncode == 1
