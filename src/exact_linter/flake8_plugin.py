"""flake8 plugin entry point: run exact's recognition engine as a flake8 check.

flake8 already handles file discovery and exclusion, so this plugin's job is
narrow: given one file (its AST and/or source lines, however flake8 hands
them over), turn its literals into flake8-style (line, col, message, type)
diagnostics. It reuses the same recognition engine, [tool.exact] config, and
--select/--ignore composition as the standalone `exact` CLI - a literal
suppressed or filtered one way is suppressed or filtered the other way too.

Sequence findings (whole-array recognition) are informational-only in the
CLI and can span many elements across several lines - that doesn't fit
flake8's single-location diagnostic model, so they're intentionally out of
scope here. Use the standalone `exact` CLI for those.
"""

from __future__ import annotations

import ast
from collections.abc import Generator
from pathlib import Path

from . import __version__
from .cli import resolve_allowed_codes
from .config import load_config
from .confidence import DEFAULT_MIN_SURPLUS
from .extract import FloatLiteral, extract_source_info
from .recognize import Match, recognize
from .triage import MIN_DIGITS, skip_reason

_FLAKE8_CODE = {"recognized": "EXA001", "truncated": "EXA002", "near-miss": "EXA003"}


def _message(code: str, literal: FloatLiteral, match: Match) -> str:
    flake8_code = _FLAKE8_CODE[code]
    if code == "near-miss":
        return (
            f"{flake8_code} {literal.text} looks like a typo for {match.form};"
            f" did you mean {match.suggestion}?"
        )
    if code == "truncated":
        return (
            f"{flake8_code} {literal.text} is {match.form}, accurate to only"
            f" {match.matched_digits} digits (~{match.precision_lost} lost);"
            f" suggest {match.suggestion}"
        )
    return f"{flake8_code} {literal.text} is {match.form}; suggest {match.suggestion}"


class ExactChecker:
    """Registered under the `flake8.extension` entry point as `EXA`."""

    name = "exact"
    version = __version__

    def __init__(
        self, tree: ast.AST, filename: str = "", lines: list[str] | None = None
    ) -> None:
        # `tree` isn't used - extract_source_info wants source text, not a
        # pre-parsed tree, and re-parsing one already-typechecked file is
        # cheap. Declared anyway because flake8 only passes constructor
        # arguments whose names it recognizes, and `tree` is how it signals
        # "this is an AST-based check" versus a physical/logical-line one.
        self._filename = filename
        self._lines = lines

    def _source(self) -> str | None:
        if self._lines:
            return "".join(self._lines)
        if self._filename and self._filename not in ("stdin", "-"):
            try:
                return Path(self._filename).read_text(encoding="utf-8")
            except OSError:
                return None
        return None

    def run(self) -> Generator[tuple[int, int, str, type], None, None]:
        source = self._source()
        if source is None:
            return
        path = Path(self._filename) if self._filename else Path("stdin.py")
        info = extract_source_info(source, path)
        config_dir = path.parent if path.parent.exists() else Path.cwd()
        config = load_config(config_dir)
        min_surplus = (
            config.min_surplus if config.min_surplus is not None else DEFAULT_MIN_SURPLUS
        )
        min_digits = config.min_digits if config.min_digits is not None else MIN_DIGITS
        allowed_codes, error = resolve_allowed_codes(
            config.select, config.ignore, config.truncation_only, config.near_miss_only
        )
        if error:  # malformed [tool.exact] codes: fail open, don't crash flake8's run
            allowed_codes = None

        for literal in info.literals:
            if literal.suppressed and literal.suppressed_codes is None:
                continue
            if skip_reason(literal, min_digits=min_digits) is not None:
                continue
            match = recognize(literal.text, min_surplus=min_surplus, extra_entries=config.constants)
            if match is None:
                continue
            code = match.code
            if literal.suppressed and literal.suppressed_codes and code in literal.suppressed_codes:
                continue
            if allowed_codes is not None and code not in allowed_codes:
                continue
            yield literal.line, literal.col, _message(code, literal, match), type(self)
