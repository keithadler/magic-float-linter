"""Command line interface: exact <paths>."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from collections.abc import Iterator, Sequence
from pathlib import Path

from .confidence import DEFAULT_MIN_SURPLUS
from .extract import extract_file
from .recognize import recognize
from .report import Finding, render_json, render_text
from .triage import skip_reason

EXCLUDED_DIRS = {
    ".git",
    ".hg",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "build",
    "dist",
    ".tox",
    ".eggs",
    "site-packages",
    ".mypy_cache",
    ".ruff_cache",
}


def iter_python_files(paths: Sequence[str]) -> Iterator[Path]:
    for raw in paths:
        path = Path(raw)
        if path.is_file() and path.suffix == ".py":
            yield path
        elif path.is_dir():
            for sub in sorted(path.rglob("*.py")):
                if not any(part in EXCLUDED_DIRS for part in sub.parts):
                    yield sub


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="exact",
        description=(
            "Find magic float constants (pi/180, 1/ln 2, 2/3, ...) in Python code"
            " and suggest exact, readable replacements."
        ),
    )
    parser.add_argument("paths", nargs="*", default=["."], help="files or directories to scan")
    parser.add_argument("--json", action="store_true", help="emit findings as JSON")
    parser.add_argument(
        "--min-surplus",
        type=float,
        default=DEFAULT_MIN_SURPLUS,
        help="evidence surplus required to report a match (default: %(default)s)",
    )
    parser.add_argument(
        "--exit-zero", action="store_true", help="exit 0 even when findings are reported"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="show counts of skipped literals"
    )
    args = parser.parse_args(argv)

    findings: list[Finding] = []
    skipped: Counter[str] = Counter()
    for file in iter_python_files(args.paths):
        for literal in extract_file(file):
            reason = skip_reason(literal)
            if reason is not None:
                skipped[reason] += 1
                continue
            match = recognize(literal.text, min_surplus=args.min_surplus)
            if match is not None:
                findings.append(Finding(literal, match))
            else:
                skipped["no confident match"] += 1

    findings.sort(key=lambda f: (str(f.literal.file), f.literal.line, f.literal.col))
    if args.json:
        print(render_json(findings))
    else:
        print(render_text(findings, dict(skipped), verbose=args.verbose))
    return 1 if findings and not args.exit_zero else 0


if __name__ == "__main__":
    sys.exit(main())
