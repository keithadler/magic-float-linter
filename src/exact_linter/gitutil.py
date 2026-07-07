"""Map which lines are new/changed, from git, for --changed-only mode."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")

ALL_LINES = frozenset()  # sentinel meaning "every line in this file is new"


def _repo_root(cwd: Path) -> Path | None:
    if shutil.which("git") is None:
        return None
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, OSError):
        return None
    return Path(result.stdout.strip())


def _parse_unified_diff(diff_text: str) -> dict[str, set[int]]:
    """Map relative-path -> set of added/changed line numbers in the new file.

    Only '+' lines count (an edited line shows as '-old'/'+new'; only the
    '+' side has a line number in the file as it exists now). Requires the
    diff to have been produced with --unified=0, so context lines never
    appear and every non-hunk-header line is either a '+' or '-' line.
    """
    changed: dict[str, set[int]] = {}
    current_file: str | None = None
    next_line: int | None = None
    for line in diff_text.splitlines():
        if line.startswith("+++ "):
            path_str = line[4:]
            if path_str == "/dev/null":
                current_file = None
            else:
                current_file = path_str[2:] if path_str[:2] in ("a/", "b/") else path_str
                changed.setdefault(current_file, set())
            next_line = None
            continue
        if line.startswith("@@"):
            m = _HUNK_RE.match(line)
            next_line = int(m.group(1)) if m else None
            continue
        if current_file is None or next_line is None:
            continue
        if line.startswith("+"):
            changed[current_file].add(next_line)
            next_line += 1
        elif line.startswith("-"):
            pass  # a removed line: doesn't exist in the new file, no line number to record
    return changed


def changed_lines(since: str | None, cwd: Path) -> dict[Path, frozenset[int]] | None:
    """Map absolute file path -> set of line numbers changed since `since`
    (or, if `since` is None, since HEAD - i.e. all uncommitted changes).

    A file's value is `ALL_LINES` (empty frozenset, checked by identity) if
    the file is untracked - new files count as entirely new. Returns None if
    this isn't a git repository or git isn't available; the caller decides
    how to handle that rather than silently scanning everything.
    """
    root = _repo_root(cwd)
    if root is None:
        return None
    # default to HEAD, not a bare `git diff`: a bare diff only shows unstaged
    # changes vs the index, missing anything already `git add`-ed
    diff_args = ["git", "-C", str(root), "diff", "--unified=0", "--no-color", since or "HEAD"]
    try:
        diff_result = subprocess.run(diff_args, capture_output=True, text=True, check=True)
        untracked_result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--others", "--exclude-standard", "--full-name"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, OSError):
        return None

    per_file = _parse_unified_diff(diff_result.stdout)
    result: dict[Path, frozenset[int]] = {
        (root / rel).resolve(): frozenset(lines) for rel, lines in per_file.items()
    }
    for rel in untracked_result.stdout.splitlines():
        if rel.endswith(".py"):
            result[(root / rel).resolve()] = ALL_LINES
    return result


def line_is_changed(changed: dict[Path, frozenset[int]], file: Path, line: int) -> bool:
    lines = changed.get(file.resolve())
    if lines is None:
        return False
    return lines is ALL_LINES or line in lines
