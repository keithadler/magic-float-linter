"""Project configuration from pyproject.toml's [tool.exact] section.

Discovery walks up from the first scanned path until a pyproject.toml with a
[tool.exact] section is found (a pyproject.toml without the section does not
stop the walk). CLI flags always override config values; config overrides
built-in defaults.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised only on Python 3.10
    import tomli as tomllib


@dataclass(frozen=True)
class Config:
    min_surplus: float | None = None
    min_digits: int | None = None
    exclude: tuple[str, ...] = ()  # fnmatch globs against the file path
    truncation_only: bool = False
    exclude_tests: bool = False
    source: Path | None = None  # the pyproject.toml the config came from


def _get(section: dict, key: str):
    # accept both snake_case and kebab-case keys
    return section.get(key, section.get(key.replace("_", "-")))


def load_config(start: Path) -> Config:
    start = start.resolve()
    if start.is_file():
        start = start.parent
    for directory in (start, *start.parents):
        pyproject = directory / "pyproject.toml"
        if not pyproject.is_file():
            continue
        try:
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError):
            return Config()
        section = data.get("tool", {}).get("exact")
        if section is None:
            continue
        return Config(
            min_surplus=_get(section, "min_surplus"),
            min_digits=_get(section, "min_digits"),
            exclude=tuple(_get(section, "exclude") or ()),
            truncation_only=bool(_get(section, "truncation_only") or False),
            exclude_tests=bool(_get(section, "exclude_tests") or False),
            source=pyproject,
        )
    return Config()
