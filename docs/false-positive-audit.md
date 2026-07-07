# False-positive audit: ordinary, non-scientific Python packages

**Date:** 2026-07-07. **Method:** installed each package into a clean Python
3.14 venv and ran `exact <site-packages>/<pkg> --exit-zero --format json`
against the installed tree. Every finding was verified by reading the source.

## Why this audit is different from the corpus study

[The corpus study](corpus-study.md) scans scientific and numeric packages -
numpy, scipy, sympy, astropy - exactly the kind of code that's *expected* to
contain real mathematical constants. Finding real bugs there proves the tool
is useful. It does not, by itself, prove the tool is *accurate*, because
that's friendly territory: a confidence gate that's a little too permissive
would still look good scanning code that's genuinely full of pi and e.

The harder, more honest test is the opposite kind of code: large, widely-used
packages that do ordinary things - HTTP requests, web routing, ORM queries,
data validation - where almost nothing should be a recognized constant at
all. If the false-positive rate holds up here, the confidence-surplus formula
is doing its job; if it doesn't, this is exactly where it would show up.

## Packages scanned

Django 6.0.7, Flask 3.1.3, requests 2.34.2, click 8.4.2, SQLAlchemy 2.0.51,
pydantic 2.13.4 - a web framework, a micro web framework, an HTTP client, a
CLI framework, an ORM, and a validation library. None are numeric or
scientific libraries; collectively they represent a large, well-audited
cross-section of ordinary application code.

## Results

| package | findings | sequences |
|---|---|---|
| Django | 1 | 0 |
| Flask | 0 | 0 |
| requests | 0 | 0 |
| click | 0 | 0 |
| SQLAlchemy | 0 | 0 |
| pydantic | 0 | 0 |

Five of the six packages produced zero findings, across their entire
installed source trees, at every recognition tier (table, rational, additive
PSLQ, log-space PSLQ) and every finding code (recognized, truncated,
near-miss, sequence). Nothing to review, nothing to argue about.

**The one finding, in Django, is correct - not a bug, and not a false
positive.** `django/contrib/gis/measure.py` defines its own unit-conversion
lookup table for the GIS module:

```python
"mi": 1609.344,
```

That's the exact, internationally defined mile-to-meters conversion factor -
matching this tool's own table entry exactly, at full precision (not
truncated). Django independently got this right. The same category as
astropy's MAD-to-sigma comment and pandas' `z95`/`z99` confidence constants
in the corpus study: the tool recognizing correct code, not finding a bug.

## What this proves, and what it doesn't

This confirms the confidence-surplus gate does not spam false positives on
ordinary application code - the harder and more meaningful accuracy claim,
since scientific/numeric packages are exactly the domain the tool is tuned
for. It does not prove the gate is perfectly calibrated in general (see the
separate Monte Carlo validation embedded in the near-miss-for-rationals work:
20,000 random mantissas, 0.01% false-positive rate, both hits landing right
at the surplus threshold as the formula predicts). Six packages is also not
an exhaustive claim - a larger audit across more of the ordinary-code
ecosystem would strengthen this further, and is a natural thing to repeat
periodically as the constant table and recognition tiers grow.

## Reproduction

```
python -m venv venv && venv/bin/pip install exact-linter django flask \
    requests click sqlalchemy pydantic
venv/bin/exact venv/lib/python3.*/site-packages/django --exit-zero -v
# repeat for flask, requests, click, sqlalchemy, pydantic
```
