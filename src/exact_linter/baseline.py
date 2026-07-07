"""Baseline snapshots: adopt the linter on a legacy codebase without a
one-time cleanup. Freeze existing findings, then only new ones are reported.

A finding is identified by (file, literal text, recognized form) - not by
line number. Line numbers drift with unrelated edits elsewhere in the file;
keying on them would re-flag baselined debt every time someone touches an
adjacent line. The trade-off: if the same literal text appears twice in one
file, both are treated as already-baselined once either one is. That's the
right default for a coarse-grained "stop the bleeding" tool - precision
takes a back seat to not re-triggering on unrelated changes.
"""

from __future__ import annotations

import json
from pathlib import Path

from .report import Finding

BASELINE_VERSION = 1

Key = tuple[str, str, str]  # (relative file, literal text, form)


def _relative(file: Path, root: Path) -> str:
    try:
        return file.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return file.as_posix()


def finding_key(finding: Finding, root: Path) -> Key:
    return (_relative(finding.literal.file, root), finding.literal.text, finding.match.form)


def load_baseline(path: Path) -> set[Key]:
    if not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    return {(e["file"], e["literal"], e["form"]) for e in data.get("entries", [])}


def write_baseline(path: Path, findings: list[Finding], root: Path) -> int:
    """Snapshot `findings` as the new baseline, replacing any existing file.
    Returns the number of unique entries written."""
    seen: set[Key] = set()
    entries = []
    for finding in findings:
        key = finding_key(finding, root)
        if key in seen:
            continue
        seen.add(key)
        entries.append({"file": key[0], "literal": key[1], "form": key[2]})
    entries.sort(key=lambda e: (e["file"], e["literal"]))
    path.write_text(
        json.dumps({"version": BASELINE_VERSION, "entries": entries}, indent=2) + "\n",
        encoding="utf-8",
    )
    return len(entries)
