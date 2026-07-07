import ast

from exact_linter.cli import main


def _run(tmp_path, source, *flags):
    f = tmp_path / "m.py"
    f.write_text(source)
    code = main([str(f), *flags])
    return f.read_text(), code


def test_fix_safe_rewrite(tmp_path, capsys):
    out, code = _run(tmp_path, "x = 3.141592653589793\n", "--fix")
    assert code == 0
    assert out == "import math\nx = math.pi\n"
    assert "1 literal(s) fixed" in capsys.readouterr().out


def test_fix_is_idempotent(tmp_path, capsys):
    _run(tmp_path, "x = 3.141592653589793\n", "--fix")
    capsys.readouterr()
    # second run over the already-fixed file changes nothing
    f = tmp_path / "m.py"
    before = f.read_text()
    main([str(f), "--fix"])
    assert f.read_text() == before


def test_fix_does_not_touch_truncated_by_default(tmp_path, capsys):
    out, _ = _run(tmp_path, "x = 3.14159\n", "--fix")
    assert out == "x = 3.14159\n"  # unchanged: not bit-identical to pi


def test_fix_truncated_opt_in(tmp_path, capsys):
    out, _ = _run(tmp_path, "x = 3.14159\n", "--fix-truncated")
    assert out == "import math\nx = math.pi\n"
    report = capsys.readouterr().out
    assert "WARNING" in report and "3.14159 -> math.pi" in report


def test_fix_wraps_for_precedence(tmp_path):
    # pi/180 has an operator; inside a division denominator it must be wrapped
    out, _ = _run(tmp_path, "y = t / 0.017453292519943295\n", "--fix")
    assert out == "import math\ny = t / (math.pi / 180)\n"
    ast.parse(out)


def test_fix_no_wrap_when_standalone(tmp_path):
    out, _ = _run(tmp_path, "R = 0.017453292519943295\n", "--fix")
    assert out == "import math\nR = math.pi / 180\n"


def test_fix_reuses_existing_math_import(tmp_path):
    out, _ = _run(tmp_path, "import math\nx = 3.141592653589793\n", "--fix")
    assert out == "import math\nx = math.pi\n"
    assert out.count("import math") == 1


def test_fix_import_after_docstring(tmp_path):
    out, _ = _run(tmp_path, '"""Module."""\nx = 3.141592653589793\n', "--fix")
    assert out == '"""Module."""\nimport math\nx = math.pi\n'


def test_fix_leaves_scipy_constants_alone(tmp_path):
    # physical constant suggestion is scipy.constants.*, not math-evaluable
    out, _ = _run(tmp_path, "c = 299792458.0\n", "--fix")
    assert out == "c = 299792458.0\n"


def test_diff_does_not_write(tmp_path, capsys):
    f = tmp_path / "m.py"
    f.write_text("x = 3.141592653589793\n")
    main([str(f), "--fix", "--diff"])
    assert f.read_text() == "x = 3.141592653589793\n"  # untouched
    out = capsys.readouterr().out
    assert "-x = 3.141592653589793" in out
    assert "+x = math.pi" in out


# --- hardening: the fixer must never corrupt a file (step 11) ---

TRICKY = [
    "a, b = 3.141592653589793, 2.718281828459045\n",  # two literals, one line
    "x = [3.141592653589793]\n",  # in a list
    "x = 3.141592653589793  # a comment\n",  # trailing comment
    "s = 'pi is 3.141592653589793'\n",  # inside a string literal - NOT a node
    "x=3.141592653589793\n",  # no spaces
    "x = 3.141592653589793\r\n",  # CRLF
    "# ééé\nx = 3.141592653589793\n",  # non-ascii on another line
    "def f():\n    return 2 * 3.141592653589793\n",  # nested in expr
]


def test_fixer_never_corrupts(tmp_path):
    for i, src in enumerate(TRICKY):
        f = tmp_path / f"t{i}.py"
        f.write_bytes(src.encode("utf-8"))
        main([str(f), "--fix", "--exit-zero"])
        result = f.read_text(encoding="utf-8")
        ast.parse(result)  # must still parse
        # the string-literal case must be left byte-identical: the digits are
        # inside a str, not a float node
        if "pi is" in src:
            assert result == src


def test_fixer_preserves_crlf(tmp_path):
    f = tmp_path / "m.py"
    f.write_bytes(b"x = 3.141592653589793\r\n")
    main([str(f), "--fix"])
    assert b"\r\n" in f.read_bytes()
