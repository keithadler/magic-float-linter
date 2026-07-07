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

## Second wave (2026-07-07): cryptography and the most-downloaded packages

The six above are ordinary application code. Two more categories are worth
pinning down, for two different reasons.

**Cryptography libraries - because "could a truncated constant be a backdoor?"
is a fair question, and this is the empirical answer.** A perturbed constant
could only be an attack vector somewhere a tiny numeric change has a
controllable effect. Cryptographic code is almost entirely integer and modular
arithmetic - there are essentially no float constants for anyone, honest or
not, to get wrong. Scanned in full:

| library | version | findings |
|---|---|---|
| cryptography | (pyca) | 0 |
| pycryptodome | | 0 |
| pynacl | | 0 |
| ecdsa | | 0 |
| rsa | | 0 |
| bcrypt | | 0 |

Zero findings across all six. There is no float-constant attack surface in
this code to inspect, which is itself the answer: this class of tool has
nothing to say about crypto, and says nothing.

**The most-downloaded PyPI packages - because the tool has to be silent on the
plumbing everyone depends on.** These are HTTP, serialization, packaging, and
cloud-SDK libraries; they move bytes, they don't do math. All scanned in full,
all zero findings:

boto3, botocore, s3transfer, jmespath, urllib3, requests, certifi,
charset-normalizer, idna, setuptools, packaging, wheel, python-dateutil, six,
pip, pyyaml, click, protobuf, attrs, typing_extensions - **22 packages, zero
findings.**

## Numerical libraries: clean, or correct-not-a-bug

The interesting frontier is numerical libraries that *aren't* the usual
suspects - places where the tool could plausibly misfire but shouldn't. Four
outcomes worth recording (2026-07-07):

- **scikit-learn: 0 findings.** The single biggest general-purpose ML/stats
  library, scanned in full, silent. Worth stating because it counters the lazy
  read of the corpus study ("science code is sloppy about constants") - the
  most-used one isn't.
- **shapely, cartopy, poliastro: 0 findings.** Geometry and astrodynamics
  libraries whose heavy math lives in compiled backends (GEOS, PROJ) or in
  computed rather than hand-typed constants.
- **pyproj and skyfield: recognized, all correct, none truncated.** pyproj's
  `pi/648000` (radians per arcsecond) and `1200/3937` (the US survey foot), and
  skyfield's `constants.py` (`pi/180`, `180/pi`, `2*pi`, the speed of light) are
  all recognized at *full* precision - the tool naming correct constants, not
  finding bugs. The same category as Django's mile factor above.
- **sgp4: one truncated constant that must NOT be "fixed."**
  `sgp4/propagation.py` contains `0.33333333` (a truncated `1/3`) in the
  deep-space resonance math. On its face a textbook truncation - but the file's
  own header states it is a deliberate, line-by-line port of Vallado's official
  C++ SGP4 reference implementation, kept faithful down to the semicolons and
  indentation, and validated bit-for-bit against the canonical NORAD test
  vectors. That `0.33333333` is verbatim from the standard. "Correcting" it to
  `1/3` would make the library *deviate* from the specified algorithm and could
  break agreement with the reference vectors. This is the same category as the
  frozen CODATA revisions and jax's backward-compat snapshots: **a truncated
  constant that is correct-as-written because it faithfully reproduces an
  external standard.** A tool that flagged it as a bug to fix would be wrong; a
  human has to know it's a port. The tool recognizes it; the judgment stays with
  the reader.

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

# second wave: crypto + most-downloaded packages (all expected to be silent)
venv/bin/pip install cryptography pycryptodome pynacl ecdsa rsa bcrypt \
    boto3 requests urllib3 setuptools packaging pyyaml click protobuf attrs
# scan each site-packages/<pkg> directory the same way

# numerical frontier
venv/bin/pip install scikit-learn pyproj shapely cartopy sgp4 skyfield poliastro
# sklearn/shapely/cartopy/poliastro: silent; pyproj/skyfield: correct
# recognitions; sgp4: one standards-faithful truncation - see above, do not fix
```
