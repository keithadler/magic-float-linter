from pathlib import Path

from exact_linter.cli import main
from exact_linter.config import load_config

PLANTED = "RAD_PER_DEG = 0.017453292519943295\n"


def test_load_config_walks_up(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[tool.exact]\nmin_surplus = 5.5\n")
    nested = tmp_path / "src" / "pkg"
    nested.mkdir(parents=True)
    config = load_config(nested)
    assert config.min_surplus == 5.5
    assert config.source == tmp_path / "pyproject.toml"


def test_load_config_kebab_case_keys(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[tool.exact]\nmin-surplus = 3.0\n")
    assert load_config(tmp_path).min_surplus == 3.0


def test_load_config_missing_section_keeps_walking(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[tool.exact]\nmin_surplus = 4.0\n")
    nested = tmp_path / "sub"
    nested.mkdir()
    (nested / "pyproject.toml").write_text("[tool.other]\nx = 1\n")
    assert load_config(nested).min_surplus == 4.0


def test_load_config_defaults_without_pyproject(tmp_path):
    config = load_config(tmp_path)
    assert config.min_surplus is None
    assert config.exclude == ()
    assert config.source is None


def test_config_min_surplus_suppresses_finding(tmp_path, capsys):
    (tmp_path / "p.py").write_text(PLANTED)
    assert main([str(tmp_path)]) == 1  # found with defaults
    capsys.readouterr()
    (tmp_path / "pyproject.toml").write_text("[tool.exact]\nmin_surplus = 99.0\n")
    assert main([str(tmp_path)]) == 0  # config gate suppresses it


def test_cli_flag_beats_config(tmp_path, capsys):
    (tmp_path / "p.py").write_text(PLANTED)
    (tmp_path / "pyproject.toml").write_text("[tool.exact]\nmin_surplus = 99.0\n")
    assert main([str(tmp_path), "--min-surplus", "2.0"]) == 1


def test_config_exclude_patterns(tmp_path, capsys):
    generated = tmp_path / "generated"
    generated.mkdir()
    (generated / "g.py").write_text(PLANTED)
    (tmp_path / "p.py").write_text(PLANTED)
    (tmp_path / "pyproject.toml").write_text('[tool.exact]\nexclude = ["generated/*"]\n')
    main([str(tmp_path), "--exit-zero"])
    out = capsys.readouterr().out
    assert "p.py" in out
    assert "g.py" not in out


def test_config_min_digits(tmp_path, capsys):
    (tmp_path / "p.py").write_text("SHORT_PI = 3.1415927\n")  # 8 digits
    assert main([str(tmp_path)]) == 1
    capsys.readouterr()
    (tmp_path / "pyproject.toml").write_text("[tool.exact]\nmin_digits = 10\n")
    assert main([str(tmp_path)]) == 0


def test_config_truncation_only(tmp_path, capsys):
    (tmp_path / "p.py").write_text("FULL = 3.141592653589793\n")
    (tmp_path / "pyproject.toml").write_text("[tool.exact]\ntruncation_only = true\n")
    assert main([str(tmp_path)]) == 0  # recognized but not truncated -> filtered


def test_config_exclude_tests(tmp_path, capsys):
    (tmp_path / "test_p.py").write_text(PLANTED)
    (tmp_path / "pyproject.toml").write_text("[tool.exact]\nexclude_tests = true\n")
    assert main([str(tmp_path)]) == 0


def test_config_bad_toml_is_ignored(tmp_path):
    (tmp_path / "pyproject.toml").write_text("this is [not toml")
    config = load_config(tmp_path)
    assert config.min_surplus is None


def test_load_config_from_file_path(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[tool.exact]\nmin_surplus = 7.0\n")
    target = tmp_path / "mod.py"
    target.write_text("x = 1\n")
    assert load_config(target).min_surplus == 7.0


def test_config_path_object_source(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[tool.exact]\nmin_surplus = 1.0\n")
    assert isinstance(load_config(tmp_path).source, Path)
