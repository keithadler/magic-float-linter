# exact

[![CI](https://github.com/keithadler/magic-float-linter/actions/workflows/ci.yml/badge.svg)](https://github.com/keithadler/magic-float-linter/actions/workflows/ci.yml)

**A linter that recognizes magic float constants and tells you what they really are.**

Codebases are full of literals like `0.017453292519943295`, `1.4426950408889634`, and
`0.3989422804014327`. Those are `pi/180`, `1/ln(2)`, and `1/sqrt(2*pi)` - but nothing in
the code says so. `exact` scans Python source, recognizes these constants, and suggests
exact, readable replacements.

```
$ exact mycode/
mycode/orbit.py:42:11  57.29577951308232  (deg_per_rad)
    = 180/pi  [use math.degrees(x) to convert radians to degrees]
    suggestion: 180 / math.pi
    confidence: matches all 16 given digits, surplus 13.9

1 recognized constant found.
```

## How it works

Float literals are extracted from the AST, aggressively triaged (short, round, or
data-like values are ignored), then run through three recognition tiers:

1. **Table lookup** - a curated library of ~140 constants: pi and friends, logarithm
   and decibel conversion factors, roots, angle conversions (arcseconds, gradians, the
   golden angle), statistics constants (z-scores, the MAD-to-sigma factor, the GELU
   coefficient), SI/CODATA physical constants, and exactly-defined unit conversions
   (mapped to `scipy.constants` names). The confidence gate charges log10(table size)
   per match, so the table can grow without inflating the false-positive rate.
2. **Rational check** - continued-fraction detection of repeating decimals like
   `0.6666666666666666` (2/3). Terminating decimals such as `0.125` are deliberately
   ignored: they are exactly representable and almost always intentional.
3. **PSLQ search** - the [PSLQ integer relation algorithm](https://www.davidhbailey.com/dhbpapers/pslq-comp-alg.pdf)
   (via `mpmath.identify`) searches for additive combinations like `(3*pi)/4` that
   the table does not cover.
4. **Log-space PSLQ** - runs PSLQ on the *logarithms* of the literal and a basis of
   small primes {2, 3, 5} and pi, which turns an additive relation among the logs
   back into a multiplicative one: monomials like `2**(1/3) / pi` that the additive
   tier's search pattern doesn't express. (The basis deliberately excludes 10, since
   `ln(10) = ln(2) + ln(5)` would make it linearly dependent on itself and PSLQ
   would just rediscover that identity instead of anything about the literal.)
   This tier is scoped to three small primes; recognizing something like
   `7/8 * (4/11)**(4/3)` - a real constant found undetected in astropy's cosmology
   module during a corpus study - would need a wider prime basis, a known limitation.

The table tier also folds each entry a few extra ways so the table covers more than
what's literally listed: **reciprocal folding** (`1/entry`, e.g. an unlisted `1/sqrt(5)`
via the listed `sqrt(5)`), **complement folding** (`1-entry`, e.g. `1 - 1/e`, the
exponential-saturation constant), and **shift folding** (`entry+1`), the last two
restricted to entries between 0 and 2 so they don't produce nonsense like "1 minus
Avogadro's number".

## Truncation detection

Recognizing a constant is only half the story. `exact` also measures how much accuracy a
literal *loses* by being written as a short decimal. `3.14159` names pi but is accurate
to only six digits inside a float that holds sixteen - the exact form would recover ten
lost digits. These are flagged as **truncated**, and they are often real precision bugs:

```
$ exact --truncation-only mycode/
mycode/geo.py:12:19  3.14159  (PI)  TRUNCATED
    = pi
    suggestion: math.pi
    precision: accurate to only 6 digits; the exact form recovers ~10 lost digits
```

Because the metric is the *magnitude* of lost precision, it even distinguishes a mistyped
constant from a merely short one: `2.71827` (a typo for e) scores worse than a correctly
rounded `2.71828`. Use `--truncation-only` to hunt precision bugs specifically.

## Near-miss detection (likely typos)

A truncation is a *faithful* short constant - `3.14159` really is pi, just shortened.
A **near-miss** is a *wrong* one: `2.71827` is close to e, but the last digit is
incorrect (e rounds to `2.71828`). That is the signature of a typo or transcription
error, and it is often a real bug:

```
$ exact --near-miss-only mycode/
mycode/consts.py:8:9  2.71827  (EULER)  LIKELY TYPO
    ~ e: close to it, but a written digit is wrong (not just short)
    suggestion: math.e  (did you mean this?)
    confidence: agrees with e to ~5 of 6 digits, then diverges
```

To keep this signal clean, near-miss detection deliberately applies only to short,
plausibly hand-typed literals against **mathematical** constants (pi, e, roots - values
that never change). It is not applied to full-precision literals (a value a
unit-in-the-last-place off a constant is a rounding artifact, not a typo) nor to physical
constants (whose CODATA revisions produce older-but-correct values that would look like
typos of the current one).

Every candidate match is gated by an **evidence score**: the digits the literal
actually provides must comfortably exceed the complexity of the claimed expression
plus the size of the space searched to find it. A 16-digit match on `pi/180` is
near-certain; a 6-digit match on some elaborate combination is a coincidence and is
suppressed. Tune the gate with `--min-surplus` (default 2.0, higher = stricter).

## Context-aware suggestions

When the literal sits inside an expression the AST can read, `exact` suggests the
idiomatic rewrite of the whole expression, not just the constant - and it adjusts
for the file's imports (`from math import pi` makes suggestions say `pi`; a missing
import gets an "add: import" note):

```
$ exact geo.py
geo.py:2:18  0.017453292519943295
    = pi/180  [use math.radians(x) to convert degrees to radians]
    suggestion: math.radians(deg)  (add: import math)  (replaces the whole expression; the constant alone is math.pi / 180)
```

Idiom rules are limited to exact algebraic identities. `x * 0.017453...` *is*
`math.radians(x)` for every x, so that rewrite is safe; but `x * 1.442695...`
(x times 1/ln 2) is `log2(e**x)`, not `log2(x)`, so no log idiom fires - the
constant's note gives the hint and leaves the judgment to the human.

## Fixing in place

`--fix` rewrites only literals whose exact form evaluates (using `math` alone)
to a bit-identical float, so it never changes what the program computes - it
just makes an exact value readable, inserting `import math` if needed:

```
$ exact --fix geo.py
$ cat geo.py
import math
R = math.pi / 180
```

`--fix-truncated` additionally rewrites truncated table constants, which
*does* change values (to the more accurate exact form), and reports each
change:

```
$ exact --fix-truncated autolev.py
2 literal(s) fixed, 0 left unchanged.
WARNING: --fix-truncated changed these values to their exact form:
  autolev.py:3  0.0174533 -> math.pi / 180
```

Add `--diff` to preview either as a unified diff without writing. Every edit is
located from the re-parsed AST and verified against the source before it is
applied; anything that does not verify is skipped, never guessed at.

## Suppressing a finding

Add a `# exact: ignore` comment on the literal's line (or on its own line directly
above) to silence it:

```python
TOLERANCE = 3.14159  # exact: ignore
```

## Install

Not yet on PyPI. From source:

```
git clone https://github.com/keithadler/magic-float-linter
cd magic-float-linter
pip install .
```

## Usage

```
exact [paths ...]        scan files or directories (default: .)
  --format {text,json,github,sarif}   output format (default: text)
  --json                 shortcut for --format json
  --truncation-only      report only constants that also lose precision
  --near-miss-only       report only likely typos (see below)
  --exclude-tests        skip test_*.py, *_test.py, and test(s)/ directories
  --min-surplus N        evidence threshold (default 2.0)
  --jobs N, -j N         scan files in N parallel processes (default 1)
  --fix                  rewrite literals whose exact form is bit-identical
  --fix-truncated        also rewrite truncated table constants (changes values)
  --diff                 with --fix, print a unified diff instead of writing
  --exit-zero            always exit 0, even with findings
  -v, --verbose          show counts of skipped literals
```

Exit code is 1 when findings are reported (flake8 convention), so it can run in CI.

For GitHub code scanning, emit SARIF and upload it:

```yaml
- run: exact src/ --format sarif --exit-zero > exact.sarif
- uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: exact.sarif
```

Truncated constants arrive as warnings; plain recognitions as notes.

`--format github` prints [GitHub Actions workflow commands](https://docs.github.com/en/actions/using-workflows/workflow-commands-for-github-actions),
so findings appear as inline annotations on a PR's Files Changed tab with no
code-scanning setup required. Truncated constants are `::warning`, others are
`::notice`. This is what the project's own CI uses to self-lint `src/`.

## What it will not flag

- Short literals (`0.5`, `1e-6`) - not enough evidence to claim anything.
- Exactly representable fractions (`0.125`) - almost always intentional.
- Values inside numeric data sequences - table data, not constants. This includes
  short tuples/lists nested inside another container (an RGB triple inside a
  colormap's list of triples, a coordinate pair inside a dict of named points) -
  the nesting itself is the signal that it's a data table entry, even though the
  inner tuple alone looks short enough to be "just a couple of constants".
- Empirical coefficients from curve fits - they satisfy no exact relation, and the
  evidence gate correctly rejects near-misses.

## Does it work on real code?

See [the corpus study](docs/corpus-study.md): nine popular scientific Python
packages, 911 recognized constants, and three verified upstream precision bugs -
sympy's AutoLev parser converting degrees with a 6-digit `0.0174533`,
scikit-image writing the CIE Lab threshold `6/29` as `0.2068966`, and
statsmodels' tricube kernel constant `70/81` as `0.864197530864`. On
scikit-image the signal-to-noise is exactly right: 1064 float literals in,
one finding out, and it's the real bug.

## Roadmap

- **Context-aware suggestions**: rewrite `x * 0.017453...` as `math.radians(x)` and
  `math.log(x) / math.log(2)` as `math.log2(x)`, using the surrounding expression.
- `--fix` mode with conservative, language-aware rewrites.
- Multi-language extraction via tree-sitter (JS, C, C++, Java).
- SARIF output for GitHub code scanning.
- Configuration via `[tool.exact]` in `pyproject.toml` (custom constants, thresholds,
  per-path ignores).

## Configuration

Settings live in `pyproject.toml` under `[tool.exact]` (discovered by walking up
from the scanned path; CLI flags always win over config):

```toml
[tool.exact]
min_surplus = 2.0        # evidence threshold (higher = stricter)
min_digits = 6           # ignore literals with fewer significant digits
exclude = ["generated/*", "vendored/*"]   # fnmatch globs
truncation_only = false
exclude_tests = false

# project-specific constants join the recognition table (and get
# truncation detection for free)
[tool.exact.constants]
plastic = { value = "1.32471795724474602596", suggestion = "PLASTIC_NUMBER", note = "plastic ratio" }
```

## pre-commit

Add to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/keithadler/magic-float-linter
    rev: main  # pin to a tag once released
    hooks:
      - id: exact
        # or: id: exact-truncation, to only flag precision-losing literals
```

## Development

```
pip install -e '.[dev]'
pytest
ruff check .
```

## License

MIT
