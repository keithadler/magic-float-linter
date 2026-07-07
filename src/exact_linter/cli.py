"""Command line interface: exact <paths>."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from collections.abc import Iterator, Sequence
from concurrent.futures import ProcessPoolExecutor
from fnmatch import fnmatch
from functools import partial
from pathlib import Path

from .confidence import DEFAULT_MIN_SURPLUS
from .config import load_config
from .extract import extract_file_info
from .idioms import idiomatic
from .recognize import recognize
from .report import Finding, adjust_for_imports, render_github, render_json, render_text
from .triage import MIN_DIGITS, skip_reason

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
                # only exclude directories found *within* the scanned tree (a
                # nested venv, a vendored build dir); ancestors of the scan
                # root itself don't count, or scanning a path that happens to
                # live inside a venv or site-packages would find nothing
                nested_dirs = sub.relative_to(path).parts[:-1]
                if not any(part in EXCLUDED_DIRS for part in nested_dirs):
                    yield sub


def is_test_file(path: Path) -> bool:
    name = path.name
    if name.startswith("test_") or name.endswith("_test.py"):
        return True
    return any(part in ("test", "tests") for part in path.parts[:-1])


def scan_file(
    file: Path, min_surplus: float, truncation_only: bool, min_digits: int = MIN_DIGITS
) -> tuple[list[Finding], dict[str, int]]:
    """Scan one file; top-level so ProcessPoolExecutor can pickle it."""
    findings: list[Finding] = []
    skipped: Counter[str] = Counter()
    info = extract_file_info(file)
    for literal in info.literals:
        if literal.suppressed:
            skipped["suppressed by comment"] += 1
            continue
        reason = skip_reason(literal, min_digits=min_digits)
        if reason is not None:
            skipped[reason] += 1
            continue
        match = recognize(literal.text, min_surplus=min_surplus)
        if match is None:
            skipped["no confident match"] += 1
        elif truncation_only and not match.truncated:
            skipped["recognized but not truncated"] += 1
        else:
            idiom = idiomatic(match, literal)
            display, import_note = adjust_for_imports(idiom or match.suggestion, info)
            findings.append(
                Finding(
                    literal,
                    match,
                    idiomatic=display if idiom else None,
                    display_suggestion="" if idiom else display,
                    import_note=import_note,
                )
            )
    return findings, dict(skipped)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="exact",
        description=(
            "Find magic float constants (pi/180, 1/ln 2, 2/3, ...) in Python code"
            " and suggest exact, readable replacements."
        ),
    )
    parser.add_argument("paths", nargs="*", default=["."], help="files or directories to scan")
    parser.add_argument(
        "--format",
        choices=["text", "json", "github"],
        default="text",
        help="output format: text, json, or github (workflow-command annotations)",
    )
    parser.add_argument("--json", action="store_true", help="shortcut for --format json")
    parser.add_argument(
        "--min-surplus",
        type=float,
        default=None,
        help=f"evidence surplus required to report a match (default: {DEFAULT_MIN_SURPLUS})",
    )
    parser.add_argument(
        "--truncation-only",
        action="store_true",
        help="report only truncated constants (magic numbers that also lose precision)",
    )
    parser.add_argument(
        "--exclude-tests",
        action="store_true",
        help="skip test files (test_*.py, *_test.py, or anything under a test/tests directory)",
    )
    parser.add_argument(
        "--exit-zero", action="store_true", help="exit 0 even when findings are reported"
    )
    parser.add_argument(
        "--jobs",
        "-j",
        type=int,
        default=1,
        help="scan files in N parallel processes (default: 1)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="show counts of skipped literals"
    )
    args = parser.parse_args(argv)

    # CLI flags override [tool.exact] in pyproject.toml; config overrides defaults
    config = load_config(Path(args.paths[0]))
    min_surplus = (
        args.min_surplus
        if args.min_surplus is not None
        else (config.min_surplus if config.min_surplus is not None else DEFAULT_MIN_SURPLUS)
    )
    min_digits = config.min_digits if config.min_digits is not None else MIN_DIGITS
    truncation_only = args.truncation_only or config.truncation_only
    exclude_tests = args.exclude_tests or config.exclude_tests

    files: list[Path] = []
    excluded_test_files = 0
    excluded_by_pattern = 0
    for file in iter_python_files(args.paths):
        if exclude_tests and is_test_file(file):
            excluded_test_files += 1
        elif any(
            fnmatch(file.as_posix(), pat) or fnmatch(file.as_posix(), f"*/{pat}")
            for pat in config.exclude
        ):
            excluded_by_pattern += 1
        else:
            files.append(file)

    worker = partial(
        scan_file,
        min_surplus=min_surplus,
        truncation_only=truncation_only,
        min_digits=min_digits,
    )
    findings: list[Finding] = []
    skipped: Counter[str] = Counter()
    if args.jobs > 1:
        with ProcessPoolExecutor(max_workers=args.jobs) as pool:
            # chunksize=1: scan cost is dominated by a few large files, so
            # batching files into chunks starves workers at the tail
            results = pool.map(worker, files, chunksize=1)
            for file_findings, file_skipped in results:
                findings.extend(file_findings)
                skipped.update(file_skipped)
    else:
        for file in files:
            file_findings, file_skipped = worker(file)
            findings.extend(file_findings)
            skipped.update(file_skipped)

    findings.sort(key=lambda f: (str(f.literal.file), f.literal.line, f.literal.col))
    output_format = "json" if args.json else args.format
    if output_format == "json":
        print(render_json(findings))
    elif output_format == "github":
        output = render_github(findings)
        if output:
            print(output)
    else:
        print(render_text(findings, dict(skipped), verbose=args.verbose))
        if args.verbose and excluded_test_files:
            print(f"\n{excluded_test_files} test file(s) excluded (--exclude-tests).")
        if args.verbose and excluded_by_pattern:
            print(f"{excluded_by_pattern} file(s) excluded by [tool.exact] exclude patterns.")
    return 1 if findings and not args.exit_zero else 0


if __name__ == "__main__":
    sys.exit(main())
