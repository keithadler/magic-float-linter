"""Scan installed packages with exact and print a markdown summary table.

Usage: python scripts/corpus_study.py numpy scipy sympy ...

Each argument is an importable package name; its installed directory is scanned
with the same pipeline the CLI uses. See docs/corpus-study.md for the study
this reproduces (findings drift as packages release new versions).
"""

from __future__ import annotations

import importlib
import sys
from collections import Counter
from pathlib import Path

from exact_linter.cli import iter_python_files
from exact_linter.extract import extract_file
from exact_linter.recognize import recognize
from exact_linter.triage import skip_reason


def scan_package(name: str) -> dict | None:
    try:
        module = importlib.import_module(name)
    except ImportError:
        print(f"  (skipping {name}: not importable in this environment)", file=sys.stderr)
        return None
    if module.__file__ is None:
        return None
    pkg_dir = Path(module.__file__).parent
    version = getattr(module, "__version__", "?")

    findings = 0
    truncated = 0
    literals = 0
    forms: Counter[str] = Counter()
    for file in iter_python_files([str(pkg_dir)]):
        for literal in extract_file(file):
            literals += 1
            if literal.suppressed or skip_reason(literal) is not None:
                continue
            match = recognize(literal.text)
            if match is None:
                continue
            findings += 1
            truncated += match.truncated
            forms[match.form] += 1
    return {
        "name": name,
        "version": version,
        "path": pkg_dir,
        "literals": literals,
        "findings": findings,
        "truncated": truncated,
        "forms": forms,
    }


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    results = [r for r in (scan_package(name) for name in argv) if r is not None]

    print("| package | version | float literals | findings | truncated |")
    print("|---|---|---|---|---|")
    for r in sorted(results, key=lambda r: -r["findings"]):
        print(
            f"| {r['name']} | {r['version']} | {r['literals']}"
            f" | {r['findings']} | {r['truncated']} |"
        )

    all_forms: Counter[str] = Counter()
    for r in results:
        all_forms.update(r["forms"])
    if all_forms:
        print("\nMost common recognized forms:")
        for form, count in all_forms.most_common(15):
            print(f"  {count:5d}  {form}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
