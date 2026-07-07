from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

import exact_linter


def test_version_matches_pyproject():
    # regression test: __init__.py's __version__ and pyproject.toml's
    # [project.version] drifted apart once already (both hardcode "0.1.0"
    # independently) - this catches it happening again.
    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    assert exact_linter.__version__ == data["project"]["version"]
