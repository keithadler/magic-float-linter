"""SARIF 2.1.0 output for GitHub code scanning."""

from __future__ import annotations

import json

from . import __version__
from .report import Finding, SequenceFinding

_RULES = (
    {
        "id": "recognized-constant",
        "name": "RecognizedConstant",
        "shortDescription": {"text": "Float literal is a known exact constant"},
        "helpUri": "https://github.com/keithadler/magic-float-linter",
        "defaultConfiguration": {"level": "note"},
    },
    {
        "id": "truncated-constant",
        "name": "TruncatedConstant",
        "shortDescription": {
            "text": "Float literal is a known constant typed with fewer digits than a float holds"
        },
        "helpUri": "https://github.com/keithadler/magic-float-linter",
        "defaultConfiguration": {"level": "warning"},
    },
    {
        "id": "recognized-sequence",
        "name": "RecognizedSequence",
        "shortDescription": {"text": "Every element of this sequence is an exact rational or constant"},
        "helpUri": "https://github.com/keithadler/magic-float-linter",
        "defaultConfiguration": {"level": "note"},
    },
)


def render_sarif(findings: list[Finding], sequence_findings: list[SequenceFinding] | None = None) -> str:
    results = []
    for finding in findings:
        lit, match = finding.literal, finding.match
        truncated = match.truncated
        message = f"{lit.text} is {match.form}; suggest {finding.suggestion}"
        if truncated:
            message += (
                f" (accurate to only {match.matched_digits} digits;"
                f" the exact form recovers ~{match.precision_lost} lost digits)"
            )
        results.append(
            {
                "ruleId": "truncated-constant" if truncated else "recognized-constant",
                "level": "warning" if truncated else "note",
                "message": {"text": message},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": lit.file.as_posix()},
                            "region": {
                                "startLine": lit.line,
                                "startColumn": lit.col + 1,
                                "endColumn": lit.col + 1 + len(lit.text),
                            },
                        }
                    }
                ],
            }
        )
    for sf in sequence_findings or ():
        seq, match = sf.sequence, sf.match
        results.append(
            {
                "ruleId": "recognized-sequence",
                "level": "note",
                "message": {"text": f"this sequence is {match.name}; suggest {match.suggestion}"},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": seq.file.as_posix()},
                            "region": {"startLine": seq.line, "startColumn": seq.col + 1},
                        }
                    }
                ],
            }
        )
    document = {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "exact",
                        "informationUri": "https://github.com/keithadler/magic-float-linter",
                        "version": __version__,
                        "rules": list(_RULES),
                    }
                },
                "results": results,
            }
        ],
    }
    return json.dumps(document, indent=2)
