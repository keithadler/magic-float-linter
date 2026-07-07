"""Render findings for humans and machines."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass

from .extract import FileInfo, FloatLiteral, NumericSequence
from .recognize import Match
from .sequences import SequenceMatch


@dataclass
class SequenceFinding:
    sequence: NumericSequence
    match: SequenceMatch


@dataclass
class Finding:
    literal: FloatLiteral
    match: Match
    # idiomatic rewrite of the literal's whole enclosing expression
    # (e.g. "math.radians(deg)"), when a context rule applies
    idiomatic: str | None = None
    # match.suggestion rewritten for the file's imports ("" = use as-is)
    display_suggestion: str = ""
    # e.g. "add: import math" when the suggestion needs an absent import
    import_note: str = ""

    @property
    def suggestion(self) -> str:
        return self.idiomatic or self.display_suggestion or self.match.suggestion


def adjust_for_imports(suggestion: str, info: FileInfo) -> tuple[str, str]:
    """Rewrite a suggestion for the file's imports and say what's missing.

    `from math import pi` makes "math.pi" render as "pi"; a suggestion that
    still references a module the file never imports gets an "add: import"
    note so the fix is copy-pasteable.
    """
    out = suggestion
    for name in info.math_names:
        out = re.sub(rf"\bmath\.{re.escape(name)}\b", name, out)
    missing = []
    for module in sorted(set(re.findall(r"\b(math|numpy|scipy\.\w+)(?=\.)", out))):
        if module.split(".")[0] not in info.modules:
            missing.append(module)
    note = f"add: import {', '.join(missing)}" if missing else ""
    return out, note


def render_text(
    findings: list[Finding],
    skipped: dict[str, int] | None = None,
    verbose: bool = False,
    sequence_findings: list[SequenceFinding] | None = None,
) -> str:
    lines: list[str] = []
    truncated_count = 0
    near_miss_count = 0
    for finding in findings:
        lit, match = finding.literal, finding.match
        location = f"{lit.file}:{lit.line}:{lit.col + 1}"
        context = f"  ({lit.context})" if lit.context else ""
        note = f"  [{match.note}]" if match.note else ""
        if match.near_miss:
            near_miss_count += 1
            lines.append(f"{location}  {lit.text}{context}  LIKELY TYPO")
            lines.append(
                f"    ~ {match.form}: close to it, but a written digit is wrong"
                f" (not just short)"
            )
            import_hint = f"  ({finding.import_note})" if finding.import_note else ""
            lines.append(f"    suggestion: {finding.suggestion}{import_hint}  (did you mean this?)")
            lines.append(
                f"    confidence: agrees with {match.form} to"
                f" ~{match.matched_digits - 1} of {match.matched_digits} digits, then diverges"
            )
            lines.append("")
            continue
        marker = "  TRUNCATED" if match.truncated else ""
        lines.append(f"{location}  {lit.text}{context}{marker}")
        lines.append(f"    = {match.form}{note}")
        import_hint = f"  ({finding.import_note})" if finding.import_note else ""
        if finding.idiomatic:
            lines.append(
                f"    suggestion: {finding.idiomatic}{import_hint}"
                f"  (replaces the whole expression; the constant alone is"
                f" {match.suggestion})"
            )
        else:
            lines.append(f"    suggestion: {finding.suggestion}{import_hint}")
        if match.truncated:
            truncated_count += 1
            lines.append(
                f"    precision: accurate to only {match.matched_digits} digits;"
                f" the exact form recovers ~{match.precision_lost} lost digits"
            )
        lines.append(
            f"    confidence: matches all {match.matched_digits} given digits,"
            f" surplus {match.surplus:.1f}"
        )
        lines.append("")
    plural = "" if len(findings) == 1 else "s"
    summary = f"{len(findings)} recognized constant{plural} found"
    qualifiers = []
    if truncated_count:
        qualifiers.append(f"{truncated_count} truncated, losing precision")
    if near_miss_count:
        qualifiers.append(f"{near_miss_count} likely typo{'' if near_miss_count == 1 else 's'}")
    if qualifiers:
        summary += f" ({'; '.join(qualifiers)})"
    lines.append(summary + ".")
    if sequence_findings:
        lines.append("")
        plural = "" if len(sequence_findings) == 1 else "s"
        lines.append(
            f"{len(sequence_findings)} exact sequence{plural} found"
            " (informational - not counted toward pass/fail):"
        )
        lines.append("")
        for sf in sequence_findings:
            seq, match = sf.sequence, sf.match
            location = f"{seq.file}:{seq.line}:{seq.col + 1}"
            lines.append(f"{location}  [{', '.join(seq.elements)}]")
            lines.append(f"    = {match.name}")
            lines.append(f"    suggestion: {match.suggestion}")
            lines.append("")
    if verbose and skipped:
        lines.append("")
        lines.append("skipped literals:")
        for reason, count in sorted(skipped.items(), key=lambda item: -item[1]):
            lines.append(f"  {count:6d}  {reason}")
    return "\n".join(lines)


def render_github(
    findings: list[Finding], sequence_findings: list[SequenceFinding] | None = None
) -> str:
    """Render as GitHub Actions workflow commands, so findings show up as
    inline PR annotations without any code-scanning setup."""
    lines = []
    for finding in findings:
        lit, match = finding.literal, finding.match
        if match.near_miss:
            level = "warning"
            message = (
                f"{lit.text} is likely a typo for {match.form};"
                f" did you mean {match.suggestion}?"
            )
        else:
            level = "warning" if match.truncated else "notice"
            message = f"{lit.text} is {match.form}; suggest {match.suggestion}"
        lines.append(f"::{level} file={lit.file},line={lit.line},col={lit.col + 1}::{message}")
    for sf in sequence_findings or ():
        seq, match = sf.sequence, sf.match
        message = f"this sequence is {match.name}; suggest {match.suggestion}"
        lines.append(f"::notice file={seq.file},line={seq.line},col={seq.col + 1}::{message}")
    return "\n".join(lines)


def render_json(
    findings: list[Finding], sequence_findings: list[SequenceFinding] | None = None
) -> str:
    payload = {"findings": [], "sequences": []}
    for finding in findings:
        item = asdict(finding.match)
        item["truncated"] = finding.match.truncated
        item["code"] = finding.match.code
        item["idiomatic"] = finding.idiomatic
        item["display_suggestion"] = finding.suggestion
        item["import_note"] = finding.import_note
        item.update(
            file=str(finding.literal.file),
            line=finding.literal.line,
            col=finding.literal.col + 1,
            literal=finding.literal.text,
            context=finding.literal.context,
        )
        payload["findings"].append(item)
    for sf in sequence_findings or ():
        payload["sequences"].append(
            {
                "file": str(sf.sequence.file),
                "line": sf.sequence.line,
                "col": sf.sequence.col + 1,
                "elements": sf.sequence.elements,
                "name": sf.match.name,
                "suggestion": sf.match.suggestion,
                "code": sf.match.code,
            }
        )
    return json.dumps(payload, indent=2)
