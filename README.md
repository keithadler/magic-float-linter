# exact

[![CI](https://github.com/keithadler/magic-float-linter/actions/workflows/ci.yml/badge.svg)](https://github.com/keithadler/magic-float-linter/actions/workflows/ci.yml)

**A linter that finds hardcoded numbers that are secretly exact mathematical
constants - typed by hand, and typed wrong.**

Here's a real one. [sympy](https://github.com/sympy/sympy) - one of the
most-downloaded packages on PyPI - has this in its AutoLev parser:

```python
# sympy/parsing/autolev/_listener_autolev_antlr.py
factor = 0.0174533   # someone typed pi/180 from memory
```

That line is supposed to be the degrees-to-radians conversion, `pi/180`. It's
accurate to 6 digits instead of the 16 a Python float actually holds - a real,
silent ~4x10⁻⁷ error, sitting in a widely-used library. `exact` finds it:

```
$ exact sympy/
sympy/parsing/autolev/_listener_autolev_antlr.py:1167:21  0.0174533  TRUNCATED
    = pi/180  [use math.radians(x) to convert degrees to radians]
    suggestion: math.pi / 180
    precision: accurate to only 6 digits; the exact form recovers ~10 lost digits
    confidence: matches all 6 given digits, surplus 3.8

1 recognized constant found (1 truncated, losing precision).
```

**This is never a deliberate trade-off.** A Python float literal is parsed once,
at compile time, into the same 64-bit double regardless of how many digits are
in the source - `0.0174533` and `math.pi / 180` cost exactly the same at
runtime. Shortening a constant's digits never buys speed; it only throws away
accuracy for free. Every truncated constant `exact` finds is someone typing
a value from memory or a reference table, not an engineering choice.

Run it the same way on your own code: `exact mycode/`.

## How it works

Float literals are extracted from the AST, aggressively triaged (short, round, or
data-like values are ignored), then run through three recognition tiers:

1. **Table lookup** - a curated library of constants: pi and friends, logarithm
   and decibel conversion factors (including the famous "3 dB" half-power point), roots,
   angle conversions (arcseconds, gradians, the golden angle), statistics constants
   (z-scores, the MAD-to-sigma factor, the GELU coefficient), CIE Lab color-science
   constants (kappa, epsilon), SI/CODATA physical constants (current and historical
   revisions - see below), and exactly-defined unit conversions, imperial and metric
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

## Historical physical constants

The 2019 SI redefinition made the Boltzmann constant, Avogadro's number,
Planck's constant, and the elementary charge *exact*, which changed the
recommended values of everything derived from them (the gas constant,
vacuum permittivity, the fine-structure constant, and more). Code written
before 2019 - or deliberately pinned to an older revision for
reproducibility - often carries the older, superseded-but-was-correct
values. `exact` recognizes several CODATA-2010 values explicitly, so they
show up as historical facts instead of being silently missed or (worse)
misdiagnosed as truncated:

```
$ exact identify 8.3144621
8.3144621 = gas constant R (CODATA 2010)
  suggestion: scipy.constants.R
  note: superseded; current CODATA value is 8.31446261815324 (exact since 2019, k and N_A are now both exact)
  confidence: matches all 8 given digits, surplus 5.9
```

This is never flagged as truncated or as a likely typo - it's the exact
value that revision recommended, not a bug. The suggestion points at
today's value for anyone who wants to modernize deliberately; `--fix` never
applies it automatically, since it isn't a bit-identical rewrite.

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

The same check applies to repeating-decimal fractions, not just named constants:
`0.333331` reads as a typo'd `1/3` (`0.333333`), the same way `2.71827` reads as a
typo'd `e`. Validated against 20,000 random mantissas before shipping: 0.01% false
positives, and both hits landed right at the confidence threshold - matching what the
evidence-score formula predicts, not a leak.

Every candidate match is gated by an **evidence score**: the digits the literal
actually provides must comfortably exceed the complexity of the claimed expression
plus the size of the space searched to find it. A 16-digit match on `pi/180` is
near-certain; a 6-digit match on some elaborate combination is a coincidence and is
suppressed. Tune the gate with `--min-surplus` (default 2.0, higher = stricter).
This isn't just argued - see [the calibration check](docs/confidence-calibration.md):
42,000 random literals, and the empirical false-positive rate came in below the
formula's own prediction at every threshold tested.

## Selecting which findings to report

Every finding has a stable **code** - `recognized`, `truncated`, `near-miss`, or
`sequence` - and `--select`/`--ignore` filter on it directly, the same
select/ignore model ruff and flake8 use:

```
$ exact --select truncated,near-miss mycode/     # only the two precision-bug codes
$ exact --ignore near-miss mycode/                # everything except near-misses
```

`--select` restricts to exactly those codes; `--ignore` removes codes from
whatever's currently allowed (everything, by default). `--truncation-only` and
`--near-miss-only` still work - they're sugar for `--select truncated` and
`--select near-miss` - but `--select` wins if both are given. Configure
persistently via `[tool.exact]` (see Configuration below).

## Whole-sequence recognition

A single literal inside a data table (`>3` numeric elements) is deliberately
never flagged on its own - most such tables are measured data, not constants.
But a sequence where **every** element is independently exact is a different
case, and worth surfacing as a unit:

```
$ exact rk4.py
rk4.py:2:15  [0.16666666666666666, 0.3333333333333333, 0.3333333333333333, 0.16666666666666666]
    = classic Runge-Kutta (RK4) weights
    suggestion: [1 / 6, 1 / 3, 1 / 3, 1 / 6]

1 exact sequence found (informational - not counted toward pass/fail):
```

A small library of iconic sequences from numerical methods (RK4 weights,
Simpson's 3/8 rule, reciprocal factorials) gets a real name; anything
else that's fully explained falls back to a generic label. Named entries are
deliberately picky about being *distinctive*, not just correct - `[0, 0.5,
0.5, 1]` looks like RK4's nodes but is common enough that it turned out to
be an FIR filter's frequency band edges in real code, so that entry was
removed rather than shipped with a misleading name. The bar is strict:
**one** unexplained element sinks the whole sequence, so this never fires on
real data tables that merely contain a few round-looking numbers by chance.

Sequence findings are informational only - they never affect the exit code and
are not subject to `--baseline`, so adopting this update can never silently
change a CI build's pass/fail result. Disable with `--no-sequences`.

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

## Adopting on a legacy codebase

Two flags exist specifically so a large existing codebase can turn `exact` on
without a big one-time cleanup:

**`--changed-only`** reports findings only on lines that are new or changed,
via git - the natural fit for a CI check on a pull request:

```
$ exact . --changed-only                 # uncommitted changes (staged + unstaged)
$ exact . --changed-only --since origin/main   # everything changed since a branch point
```

New (untracked) files are scanned in full. Requires being run inside a git
repository.

**`--baseline`** snapshots today's findings and only reports new ones from
then on:

```
$ exact . --baseline .exact-baseline.json --update-baseline   # freeze current debt
$ exact . --baseline .exact-baseline.json                     # CI: fail only on new findings
```

A baselined finding is matched by file, literal text, and recognized form -
deliberately not by line number, so unrelated edits elsewhere in the file
don't un-baseline it. Run `exact` from the same directory both times (the
path argument, not the shell's cwd, is what baseline entries are stored
relative to).

## Identifying a single number

`exact identify <number>` explains one value directly - the Inverse Symbolic
Calculator, as a terminal command, for whatever number you're staring at right
now instead of one buried in a file:

```
$ exact identify 0.2068966
0.2068966 = 6/29 - truncated
  suggestion: 6 / 29
  note: repeating decimal
  precision: accurate to only 7 digits; the exact form recovers ~9 lost digits
  confidence: matches all 7 given digits, surplus 2.0
```

Takes `--min-surplus` and `--json` like the main scan.

## Suppressing a finding

Add a `# exact: ignore` comment on the literal's line (or on its own line directly
above) to silence it. A bracketed code list narrows that to specific codes only,
using the same vocabulary as `--select`/`--ignore`:

```python
TOLERANCE = 3.14159             # exact: ignore                  (silences everything)
TOLERANCE = 3.14159             # exact: ignore[truncated]        (only the truncation finding)
EULER = 2.71827                 # exact: ignore[near-miss]        (only the typo finding)
```

## Install

Directly from GitHub (works today, no clone needed):

```
pip install "git+https://github.com/keithadler/magic-float-linter"
```

Or with [pipx](https://pipx.pypa.io/) to get the `exact` command on its own:

```
pipx install "git+https://github.com/keithadler/magic-float-linter"
```

A PyPI release (`pip install exact-linter`) is prepared and coming; until then
the GitHub URL above is the canonical install. From a local clone, `pip install .`
works the same way.

## Usage

```
exact [paths ...]        scan files or directories (default: .)
  --format {text,json,github,sarif}   output format (default: text)
  --json                 shortcut for --format json
  --truncation-only      report only constants that also lose precision
  --near-miss-only       report only likely typos (see below)
  --select CODES         report only these codes (comma-separated: recognized,
                         truncated, near-miss, sequence)
  --ignore CODES         never report these codes (comma-separated)
  --exclude-tests        skip test_*.py, *_test.py, and test(s)/ directories
  --min-surplus N        evidence threshold (default 2.0)
  --jobs N, -j N         scan files in N parallel processes (default 1)
  --changed-only         only report findings on lines changed since --since
  --since REF            git ref to diff against for --changed-only (default: HEAD)
  --baseline PATH        only report findings not already in this baseline file
  --update-baseline      write current findings to --baseline instead of reporting
  --fix                  rewrite literals whose exact form is bit-identical
  --fix-truncated        also rewrite truncated table constants (changes values)
  --diff                 with --fix, print a unified diff instead of writing
  --no-sequences         skip whole-sequence recognition (see below)
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

## GitHub Action

No install step needed in your own workflow - this repo ships as an action:

```yaml
- uses: keithadler/magic-float-linter@v0.2.0
  with:
    paths: src/                                  # default: .
    # format: github                             # text, json, github, or sarif
    # args: --select truncated,near-miss          # any extra exact flags
    # fail-on-findings: 'false'                   # informational only, never fails the job
```

It installs `exact` from the pinned ref itself (not PyPI - works today, and stays
version-consistent with whatever ref you pin), then runs it and surfaces findings as
inline annotations by default. Pin to a tag (`@v0.2.0`) for stability or `@main` for
the latest.

## What it will not flag

- Short literals (`0.5`, `1e-6`) - not enough evidence to claim anything.
- Exactly representable fractions (`0.125`) - almost always intentional.
- Values inside numeric data sequences - table data, not constants, individually.
  This includes short tuples/lists nested inside another container (an RGB triple
  inside a colormap's list of triples, a coordinate pair inside a dict of named
  points) - the nesting itself is the signal that it's a data table entry, even
  though the inner tuple alone looks short enough to be "just a couple of
  constants". A flat sequence where *every* element is independently exact is
  still surfaced, as a whole unit - see "Whole-sequence recognition" above.
- Empirical coefficients from curve fits - they satisfy no exact relation, and the
  evidence gate correctly rejects near-misses.

## Does it work on real code?

The sympy bug above isn't a one-off. See [the corpus study](docs/corpus-study.md):
nine popular scientific Python packages, and four verified upstream precision
bugs found so far - sympy's AutoLev conversion, scikit-image writing the CIE
Lab threshold `6/29` as `0.2068966`, statsmodels' tricube kernel constant
`70/81` as `0.864197530864`, and **Pillow** hardcoding the inches-per-meter
conversion as `39.3701` in `BmpImagePlugin.py` (both the BMP read and write
paths) instead of the exact `39.37007874015748` - one of the most-installed
packages on PyPI. On scikit-image the signal-to-noise is exactly right: 1064
float literals in, one finding out, and it's the real bug.

That's the "finds real bugs" claim. The other half - "doesn't spam false positives
on code that was never expected to have magic floats" - was checked separately
against Django, Flask, requests, click, SQLAlchemy, and pydantic: none of these
are numeric or scientific libraries, so almost nothing should fire. Five of the
six produced zero findings. The one hit, in Django's GIS module, is a correct
recognition of an exact conversion factor Django itself gets right (not a bug) -
see [the false-positive audit](docs/false-positive-audit.md) for the full writeup.
That audit was then scaled to [**100** popular non-scientific packages](docs/false-positive-audit-100.md) -
frameworks, HTTP clients, ORMs, cloud SDKs, dev tools - and produced exactly
**one** finding across all of them: the same correct Django factor. Ninety-eight
other large codebases, zero findings; zero truncations, zero near-misses, zero
false positives.

The scan was later pushed into AI/ML code - [torch, transformers, jax, xgboost,
keras, onnx and more](docs/ai-ml-corpus-study.md). Two more genuine, verified
truncations turned up: Hugging Face Transformers hardcoding `1/ln(2)` as
`1.442695041` in the TimesFM and VideoPrism attention math (eight locations,
confirmed still live on `main`), and ONNX's reference classifier writing
`sqrt(2)` as `1.41421356`. Both are real and both are honestly *low-impact* -
the error sits far below float32's own precision - which the write-up says
plainly rather than dressing them up.

Underneath both of those sits the confidence-surplus formula itself, checked
directly rather than just through its effects: [42,000 random literals](docs/confidence-calibration.md),
and the empirical false-positive rate came in below the formula's own prediction
at every threshold tested - including a close, honest look at every hit that
landed anywhere near the default gate.

## Scope and limitations

To set expectations honestly, before you run it:

- **It finds one specific thing:** decimal literals that are secretly exact
  math or physics constants, typed by hand - and, among those, the ones typed
  short (truncated) or wrong (near-miss). That's the whole job.
- **It is not a severity ranker.** A truncation is a fact about precision, not a
  measure of harm. Most truncations found in the wild are harmless - the error
  is often far below the working precision of the surrounding computation. The
  tool reports the precision fact; deciding whether it *matters* is yours. The
  one place it clearly mattered (sympy) is the exception that motivated the
  tool, not the rule.
- **"Recognized" is not "wrong."** Naming a full-precision `math.pi/180` written
  as a decimal is a readability suggestion, not a bug report. Only `truncated`
  and `near-miss` point at possible defects.
- **Some truncations are correct-as-written.** A constant that faithfully
  reproduces an external standard - a frozen CODATA revision, a bit-for-bit port
  of a reference algorithm like SGP4 - should *not* be "fixed," because
  faithfulness to the spec outranks mathematical exactness. The tool recognizes
  these; a human has to supply the context. See the
  [false-positive audit](docs/false-positive-audit.md) for worked examples.
- **It lives where constants are hand-typed:** scientific, numerical, graphics,
  and ML code. On ordinary application code, crypto, and infrastructure it is -
  correctly - almost entirely silent. Scanned across ~40 packages, it produced
  two consequential-enough findings, a handful of low-impact ones, and no
  false alarms on non-numerical code.
- **Python only, for now** (multi-language extraction is on the roadmap), and
  it reads *literals in source* - not values computed at runtime, loaded from
  data, or produced by a fit.

## Roadmap

- Multi-language extraction via tree-sitter (JS, C, C++, Java).
- PyPI release.

## Configuration

Settings live in `pyproject.toml` under `[tool.exact]` (discovered by walking up
from the scanned path; CLI flags always win over config):

```toml
[tool.exact]
min_surplus = 2.0        # evidence threshold (higher = stricter)
min_digits = 6           # ignore literals with fewer significant digits
exclude = ["generated/*", "vendored/*"]   # fnmatch globs
truncation_only = false
near_miss_only = false
select = []               # e.g. ["truncated", "near-miss"] - restrict to just these
ignore = []                # e.g. ["near-miss"] - never report these
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

## flake8

`exact` registers itself as a flake8 plugin automatically on install (no config
needed) - it rides inside a pipeline you're already running, prefixed `EXA`:

```
$ flake8 --select=EXA mycode/
mycode/orbit.py:42:11: EXA002 57.29577951308232 is 180/pi, accurate to only...
```

- `EXA001` recognized, `EXA002` truncated, `EXA003` near-miss (likely typo).
- Uses the same `[tool.exact]` config, `--select`/`--ignore` composition, and
  `# exact: ignore[code]` suppression as the standalone CLI - a literal treated
  one way by `exact` is treated the same way by flake8.
- Whole-sequence recognition is intentionally out of scope here: it can span
  many elements across several lines, which doesn't fit flake8's
  single-location diagnostic model. Use the standalone CLI for that.

## Development

```
pip install -e '.[dev]'
pytest
ruff check .
```

## License

MIT
