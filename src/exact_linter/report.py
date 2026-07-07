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


def render_text(
    findings: list[Finding],
    skipped: dict[str, int] | None = None,
    verbose: bool = False,
) -> str:
    lines: list[str] = []
    for finding in findings:
        lit, match = finding.literal, finding.match
        location = f"{lit.file}:{lit.line}:{lit.col + 1}"
        context = f"  ({lit.context})" if lit.context else ""
        note = f"  [{match.note}]" if match.note else ""
        lines.append(f"{location}  {lit.text}{context}")
        lines.append(f"    = {match.form}{note}")
        lines.append(f"    suggestion: {match.suggestion}")
        lines.append(
            f"    confidence: matches all {match.matched_digits} given digits,"
            f" surplus {match.surplus:.1f}"
        )
        lines.append("")
    plural = "" if len(findings) == 1 else "s"
    lines.append(f"{len(findings)} recognized constant{plural} found.")
    if verbose and skipped:
        lines.append("")
        lines.append("skipped literals:")
        for reason, count in sorted(skipped.items(), key=lambda item: -item[1]):
            lines.append(f"  {count:6d}  {reason}")
    return "\n".join(lines)


def render_json(findings: list[Finding]) -> str:
    payload = []
    for finding in findings:
        item = asdict(finding.match)
        item.update(
            file=str(finding.literal.file),
            line=finding.literal.line,
            col=finding.literal.col + 1,
            literal=finding.literal.text,
            context=finding.literal.context,
        )
        payload.append(item)
    return json.dumps(payload, indent=2)
