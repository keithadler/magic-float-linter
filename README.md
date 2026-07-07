# exact

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
   (via `mpmath.identify`) searches for combinations like `(3*pi)/4` that the table
   does not cover.

The table tier also does **reciprocal folding**: a literal that is `1/entry` for any
table entry is recognized even when only the plain form is listed, so every reciprocal
is covered for free.

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

Every candidate match is gated by an **evidence score**: the digits the literal
actually provides must comfortably exceed the complexity of the claimed expression
plus the size of the space searched to find it. A 16-digit match on `pi/180` is
near-certain; a 6-digit match on some elaborate combination is a coincidence and is
suppressed. Tune the gate with `--min-surplus` (default 2.0, higher = stricter).

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
  --json                 machine-readable output
  --truncation-only      report only constants that also lose precision
  --min-surplus N        evidence threshold (default 2.0)
  --exit-zero            always exit 0, even with findings
  -v, --verbose          show counts of skipped literals
```

Exit code is 1 when findings are reported (flake8 convention), so it can run in CI.

## What it will not flag

- Short literals (`0.5`, `1e-6`) - not enough evidence to claim anything.
- Exactly representable fractions (`0.125`) - almost always intentional.
- Values inside numeric data sequences - table data, not constants.
- Empirical coefficients from curve fits - they satisfy no exact relation, and the
  evidence gate correctly rejects near-misses.

## Roadmap

- **Context-aware suggestions**: rewrite `x * 0.017453...` as `math.radians(x)` and
  `math.log(x) / math.log(2)` as `math.log2(x)`, using the surrounding expression.
- `--fix` mode with conservative, language-aware rewrites.
- Multi-language extraction via tree-sitter (JS, C, C++, Java).
- SARIF output for GitHub code scanning.
- Configuration via `[tool.exact]` in `pyproject.toml` (custom constants, thresholds,
  per-path ignores) and inline `# exact: ignore` suppression.

## Development

```
pip install -e '.[dev]'
pytest
ruff check .
```

## License

MIT
