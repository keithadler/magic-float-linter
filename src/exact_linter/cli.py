"""Command line interface: exact <paths>."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import asdict
from collections.abc import Iterator, Sequence
from concurrent.futures import ProcessPoolExecutor
from fnmatch import fnmatch
from functools import partial
from pathlib import Path

from .baseline import finding_key, load_baseline, write_baseline
from .confidence import DEFAULT_MIN_SURPLUS
from .config import load_config
from .extract import extract_file_info
from .gitutil import changed_lines, line_is_changed
from .idioms import idiomatic
from .recognize import recognize
from .report import (
    Finding,
    SequenceFinding,
    adjust_for_imports,
    render_github,
    render_json,
    render_text,
)
from .sequences import MIN_SEQUENCE_LENGTH, identify_sequence
from .triage import MIN_DIGITS, skip_reason

# stable finding categories for --select/--ignore and per-line
# "# exact: ignore[code]" suppression (see recognize.Match.code / sequences.CODE)
CODES = ("recognized", "truncated", "near-miss", "sequence")

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
    file: Path,
    min_surplus: float,
    allowed_codes: frozenset[str] | None,
    min_digits: int = MIN_DIGITS,
    extra_entries: tuple = (),
    find_sequences: bool = True,
) -> tuple[list[Finding], list[SequenceFinding], dict[str, int]]:
    """Scan one file; top-level so ProcessPoolExecutor can pickle it.

    `allowed_codes` is the result of resolving --select/--ignore (and the
    --truncation-only/--near-miss-only shortcuts, which are sugar for it) -
    None means every code is allowed.
    """
    findings: list[Finding] = []
    skipped: Counter[str] = Counter()
    info = extract_file_info(file)
    for literal in info.literals:
        # the bare "suppress everything" case is checked here, before the
        # (cached but not free) recognition search, exactly as before this
        # feature existed. Code-specific suppression ("ignore[truncated]")
        # can't be resolved until the match - and its code - is known, so
        # that check is deferred below.
        if literal.suppressed and literal.suppressed_codes is None:
            skipped["suppressed by comment"] += 1
            continue
        reason = skip_reason(literal, min_digits=min_digits)
        if reason is not None:
            skipped[reason] += 1
            continue
        match = recognize(literal.text, min_surplus=min_surplus, extra_entries=extra_entries)
        if match is None:
            skipped["no confident match"] += 1
            continue
        code = match.code
        if literal.suppressed and code in literal.suppressed_codes:
            skipped["suppressed by comment"] += 1
            continue
        if allowed_codes is not None and code not in allowed_codes:
            skipped[f"excluded by --select/--ignore ({code})"] += 1
            continue
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

    sequence_findings: list[SequenceFinding] = []
    if find_sequences and (allowed_codes is None or "sequence" in allowed_codes):
        for seq in info.sequences:
            if len(seq.elements) < MIN_SEQUENCE_LENGTH:
                continue
            seq_match = identify_sequence(seq, min_surplus)
            if seq_match is not None:
                sequence_findings.append(SequenceFinding(seq, seq_match))

    return findings, sequence_findings, dict(skipped)


def _run_fixes(findings: list[Finding], fix_truncated: bool, diff: bool) -> int:
    import difflib
    from collections import defaultdict as _dd

    from .fix import fix_source

    by_file: dict[Path, list[Finding]] = _dd(list)
    for finding in findings:
        by_file[finding.literal.file].append(finding)

    total_applied = total_skipped = 0
    value_changes: list[tuple[Path, int, str, str]] = []
    for file, file_findings in sorted(by_file.items(), key=lambda kv: str(kv[0])):
        try:
            # bytes, not read_text: preserve CRLF exactly (no newline translation)
            source = file.read_bytes().decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        result = fix_source(source, file_findings, fix_truncated=fix_truncated)
        total_applied += result.applied
        total_skipped += result.skipped
        if result.applied == 0:
            continue
        if fix_truncated:
            for line, old, new in result.changes:
                if float(old) != _safe_eval(new):
                    value_changes.append((file, line, old, new))
        if diff:
            sys.stdout.writelines(
                difflib.unified_diff(
                    source.splitlines(keepends=True),
                    result.new_source.splitlines(keepends=True),
                    fromfile=str(file),
                    tofile=str(file),
                )
            )
        else:
            file.write_bytes(result.new_source.encode("utf-8"))

    verb = "would fix" if diff else "fixed"
    print(f"\n{total_applied} literal(s) {verb}, {total_skipped} left unchanged.")
    if value_changes and not diff:
        print("WARNING: --fix-truncated changed these values to their exact form:")
        for file, line, old, new in value_changes:
            print(f"  {file}:{line}  {old} -> {new}")
    return 0


def _parse_code_list(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return ()
    return tuple(c.strip() for c in raw.split(",") if c.strip())


def resolve_allowed_codes(
    select: tuple[str, ...],
    ignore: tuple[str, ...],
    truncation_only: bool,
    near_miss_only: bool,
) -> tuple[frozenset[str] | None, str | None]:
    """Resolve --select/--ignore - plus --truncation-only/--near-miss-only,
    which are sugar for --select - into the codes scan_file should report.

    Returns (allowed_codes, error_message); allowed_codes is None when every
    code is allowed. error_message is set only when an unknown code was
    given, in which case allowed_codes is meaningless and the caller should
    print the error and exit.
    """
    for code in (*select, *ignore):
        if code not in CODES:
            return None, f"unknown finding code {code!r} (choices: {', '.join(CODES)})"

    if select:
        allowed: frozenset[str] | None = frozenset(select)
    elif truncation_only or near_miss_only:
        shortcut = set()
        if truncation_only:
            shortcut.add("truncated")
        if near_miss_only:
            shortcut.add("near-miss")
        allowed = frozenset(shortcut)
    else:
        allowed = None

    if ignore:
        allowed = frozenset(CODES if allowed is None else allowed) - frozenset(ignore)

    return allowed, None


def _safe_eval(expr: str) -> float:
    import math

    try:
        return float(eval(expr, {"__builtins__": {}, "math": math}))
    except Exception:
        return float("nan")


def _run_identify(argv: Sequence[str]) -> int:
    """`exact identify <number>`: explain one value directly, no file scan.

    The one-shot "what is this number" query - the Inverse Symbolic
    Calculator, as a terminal command, for whatever value you're staring at
    right now instead of one buried in a source file.
    """
    parser = argparse.ArgumentParser(
        prog="exact identify",
        description="Identify a single float value as an exact form.",
    )
    parser.add_argument("value", help="the number to identify, e.g. 0.2068966")
    parser.add_argument(
        "--min-surplus",
        type=float,
        default=None,
        help=f"evidence surplus required to report a match (default: {DEFAULT_MIN_SURPLUS})",
    )
    parser.add_argument("--json", action="store_true", help="emit as JSON")
    args = parser.parse_args(argv)

    try:
        float(args.value)
    except ValueError:
        print(f"error: {args.value!r} is not a number", file=sys.stderr)
        return 2

    min_surplus = args.min_surplus if args.min_surplus is not None else DEFAULT_MIN_SURPLUS
    match = recognize(args.value, min_surplus=min_surplus)

    if args.json:
        print(json.dumps(asdict(match) if match else None, indent=2))
        return 0 if match else 1

    if match is None:
        print(f"{args.value}: no confident match")
        return 1

    tag = " - LIKELY TYPO" if match.near_miss else (" - truncated" if match.truncated else "")
    print(f"{args.value} = {match.form}{tag}")
    print(f"  suggestion: {match.suggestion}")
    if match.note:
        print(f"  note: {match.note}")
    if match.truncated:
        print(
            f"  precision: accurate to only {match.matched_digits} digits;"
            f" the exact form recovers ~{match.precision_lost} lost digits"
        )
    print(f"  confidence: matches all {match.matched_digits} given digits, surplus {match.surplus:.1f}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    raw_argv = sys.argv[1:] if argv is None else list(argv)
    if raw_argv[:1] == ["identify"]:
        return _run_identify(raw_argv[1:])

    parser = argparse.ArgumentParser(
        prog="exact",
        description=(
            "Find magic float constants (pi/180, 1/ln 2, 2/3, ...) in Python code"
            " and suggest exact, readable replacements."
            "\n\nTip: `exact identify <number>` explains a single value directly,"
            " without scanning any files."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("paths", nargs="*", default=["."], help="files or directories to scan")
    parser.add_argument(
        "--format",
        choices=["text", "json", "github", "sarif"],
        default="text",
        help=(
            "output format: text, json, github (workflow-command annotations),"
            " or sarif (GitHub code scanning)"
        ),
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
        "--near-miss-only",
        action="store_true",
        help="report only near-misses (literals that look like a typo'd known constant)",
    )
    parser.add_argument(
        "--select",
        default=None,
        help=(
            "report only these finding codes, comma-separated"
            f" (choices: {', '.join(CODES)}). Takes precedence over"
            " --truncation-only/--near-miss-only if both are given"
        ),
    )
    parser.add_argument(
        "--ignore",
        default=None,
        help="never report these finding codes, comma-separated (same choices as --select)",
    )
    parser.add_argument(
        "--exclude-tests",
        action="store_true",
        help="skip test files (test_*.py, *_test.py, or anything under a test/tests directory)",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="rewrite literals whose exact form is bit-identical (safe, no value change)",
    )
    parser.add_argument(
        "--fix-truncated",
        action="store_true",
        help="also rewrite truncated table constants (CHANGES values to the exact form)",
    )
    parser.add_argument(
        "--diff",
        action="store_true",
        help="with --fix/--fix-truncated, print a unified diff instead of writing files",
    )
    parser.add_argument(
        "--changed-only",
        action="store_true",
        help=(
            "only report findings on lines changed since --since (default: HEAD,"
            " i.e. uncommitted changes); requires a git repository"
        ),
    )
    parser.add_argument(
        "--since",
        default=None,
        help="git ref to diff against for --changed-only (default: HEAD)",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=None,
        help="path to a baseline file; only findings not already in it are reported",
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="write current findings to --baseline instead of reporting them",
    )
    parser.add_argument(
        "--no-sequences",
        action="store_true",
        help=(
            "skip whole-sequence recognition (e.g. Runge-Kutta weight vectors)."
            " Sequence findings are informational: they never affect the exit code"
        ),
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
    if args.update_baseline and args.baseline is None:
        print("error: --update-baseline requires --baseline PATH", file=sys.stderr)
        return 2
    if args.since and not args.changed_only:
        print("error: --since only applies with --changed-only", file=sys.stderr)
        return 2

    # CLI flags override [tool.exact] in pyproject.toml; config overrides defaults
    config = load_config(Path(args.paths[0]))
    min_surplus = (
        args.min_surplus
        if args.min_surplus is not None
        else (config.min_surplus if config.min_surplus is not None else DEFAULT_MIN_SURPLUS)
    )
    min_digits = config.min_digits if config.min_digits is not None else MIN_DIGITS
    truncation_only = args.truncation_only or config.truncation_only
    near_miss_only = args.near_miss_only or config.near_miss_only
    select = _parse_code_list(args.select) or config.select
    ignore = _parse_code_list(args.ignore) or config.ignore
    allowed_codes, code_error = resolve_allowed_codes(
        select, ignore, truncation_only, near_miss_only
    )
    if code_error:
        print(f"error: {code_error}", file=sys.stderr)
        return 2
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
        allowed_codes=allowed_codes,
        min_digits=min_digits,
        extra_entries=config.constants,
        find_sequences=not args.no_sequences,
    )
    findings: list[Finding] = []
    sequence_findings: list[SequenceFinding] = []
    skipped: Counter[str] = Counter()
    if args.jobs > 1:
        with ProcessPoolExecutor(max_workers=args.jobs) as pool:
            # chunksize=1: scan cost is dominated by a few large files, so
            # batching files into chunks starves workers at the tail
            results = pool.map(worker, files, chunksize=1)
            for file_findings, file_sequence_findings, file_skipped in results:
                findings.extend(file_findings)
                sequence_findings.extend(file_sequence_findings)
                skipped.update(file_skipped)
    else:
        for file in files:
            file_findings, file_sequence_findings, file_skipped = worker(file)
            findings.extend(file_findings)
            sequence_findings.extend(file_sequence_findings)
            skipped.update(file_skipped)

    findings.sort(key=lambda f: (str(f.literal.file), f.literal.line, f.literal.col))
    sequence_findings.sort(key=lambda f: (str(f.sequence.file), f.sequence.line, f.sequence.col))

    # the directory --changed-only and --baseline resolve paths relative to:
    # the scanned path, not the process's cwd, which differ whenever exact is
    # invoked with an explicit path (or, in tests, when the test process's cwd
    # is this repo but the scan target is an unrelated tmp_path)
    scan_root = Path(args.paths[0])
    scan_root = scan_root if scan_root.is_dir() else scan_root.parent

    excluded_unchanged = 0
    if args.changed_only:
        changed = changed_lines(args.since, scan_root)
        if changed is None:
            print(
                "error: --changed-only requires a git repository (git not found,"
                " or not run inside one)",
                file=sys.stderr,
            )
            return 2
        kept = []
        for finding in findings:
            if line_is_changed(changed, finding.literal.file, finding.literal.line):
                kept.append(finding)
            else:
                excluded_unchanged += 1
        findings = kept
        sequence_findings = [
            sf
            for sf in sequence_findings
            if line_is_changed(changed, sf.sequence.file, sf.sequence.line)
        ]

    excluded_baselined = 0
    if args.update_baseline:
        written = write_baseline(args.baseline, findings, scan_root)
        print(f"baseline written to {args.baseline}: {written} entries.")
        return 0
    if args.baseline is not None:
        known = load_baseline(args.baseline)
        kept = []
        for finding in findings:
            if finding_key(finding, scan_root) in known:
                excluded_baselined += 1
            else:
                kept.append(finding)
        findings = kept

    if args.fix or args.fix_truncated:
        return _run_fixes(findings, fix_truncated=args.fix_truncated, diff=args.diff)

    output_format = "json" if args.json else args.format
    if output_format == "json":
        print(render_json(findings, sequence_findings))
    elif output_format == "sarif":
        from .sarif import render_sarif

        print(render_sarif(findings, sequence_findings))
    elif output_format == "github":
        output = render_github(findings, sequence_findings)
        if output:
            print(output)
    else:
        print(
            render_text(
                findings, dict(skipped), verbose=args.verbose, sequence_findings=sequence_findings
            )
        )
        if args.verbose and excluded_test_files:
            print(f"\n{excluded_test_files} test file(s) excluded (--exclude-tests).")
        if args.verbose and excluded_by_pattern:
            print(f"{excluded_by_pattern} file(s) excluded by [tool.exact] exclude patterns.")
        if args.verbose and excluded_unchanged:
            print(f"{excluded_unchanged} finding(s) outside changed lines (--changed-only).")
        if args.verbose and excluded_baselined:
            print(f"{excluded_baselined} finding(s) already in the baseline.")
    return 1 if findings and not args.exit_zero else 0


if __name__ == "__main__":
    sys.exit(main())
