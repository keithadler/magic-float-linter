"""Render findings for humans and machines."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from .extract import FloatLiteral
from .recognize import Match


@dataclass
class Finding:
    literal: FloatLiteral
    match: Match
    # idiomatic rewrite of the literal's whole enclosing expression
    # (e.g. "math.radians(deg)"), when a context rule applies
    idiomatic: str | None = None


def render_text(
    findings: list[Finding],
    skipped: dict[str, int] | None = None,
    verbose: bool = False,
) -> str:
    lines: list[str] = []
    truncated_count = 0
    for finding in findings:
        lit, match = finding.literal, finding.match
        location = f"{lit.file}:{lit.line}:{lit.col + 1}"
        context = f"  ({lit.context})" if lit.context else ""
        note = f"  [{match.note}]" if match.note else ""
        marker = "  TRUNCATED" if match.truncated else ""
        lines.append(f"{location}  {lit.text}{context}{marker}")
        lines.append(f"    = {match.form}{note}")
        if finding.idiomatic:
            lines.append(
                f"    suggestion: {finding.idiomatic}"
                f"  (replaces the whole expression; the constant alone is"
                f" {match.suggestion})"
            )
        else:
            lines.append(f"    suggestion: {match.suggestion}")
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
    if truncated_count:
        summary += f" ({truncated_count} truncated, losing precision)"
    lines.append(summary + ".")
    if verbose and skipped:
        lines.append("")
        lines.append("skipped literals:")
        for reason, count in sorted(skipped.items(), key=lambda item: -item[1]):
            lines.append(f"  {count:6d}  {reason}")
    return "\n".join(lines)


def render_github(findings: list[Finding]) -> str:
    """Render as GitHub Actions workflow commands, so findings show up as
    inline PR annotations without any code-scanning setup."""
    lines = []
    for finding in findings:
        lit, match = finding.literal, finding.match
        level = "warning" if match.truncated else "notice"
        message = f"{lit.text} is {match.form}; suggest {match.suggestion}"
        lines.append(f"::{level} file={lit.file},line={lit.line},col={lit.col + 1}::{message}")
    return "\n".join(lines)


def render_json(findings: list[Finding]) -> str:
    payload = []
    for finding in findings:
        item = asdict(finding.match)
        item["truncated"] = finding.match.truncated
        item["idiomatic"] = finding.idiomatic
        item.update(
            file=str(finding.literal.file),
            line=finding.literal.line,
            col=finding.literal.col + 1,
            literal=finding.literal.text,
            context=finding.literal.context,
        )
        payload.append(item)
    return json.dumps(payload, indent=2)
