# Changelog

## 0.2.0 (unreleased)

Everything since 0.1.0. The engine, the CLI surface, and the constant table
all grew substantially; this is effectively the tool's first "real" release.

### New recognition capabilities

- **Truncation detection**: flags a literal that faithfully names a constant
  but was typed with fewer digits than a double holds (`3.14159` for pi), and
  reports how many digits were lost.
- **Near-miss (typo) detection**: flags a literal that is *close* to a known
  constant but is not its correct rounding or truncation - the signature of a
  transcription error (`2.71827` for e, a wrong digit, not just a short one).
  `--near-miss-only` isolates these.
- **Reciprocal, complement, and shift folding**: recognizes `1/x`, `1-x`, and
  `x+1` for any table entry, without doubling the table's size.
- **Log-space PSLQ tier**: catches multiplicative relations (`8/pi`,
  `2**(1/3)/pi`) the original additive-only search couldn't express. Basis
  widened from `{2,3,5}` to `{2,3,5,7,11}` after the corpus study found a
  real, human-documented constant needing the wider basis.
- **Whole-sequence recognition**: a flat numeric sequence (list/tuple/set)
  where *every* element is independently exact - a Runge-Kutta weight
  vector, a run of reciprocal factorials - is recognized as a unit and named
  from a small library of iconic sequences from numerical methods.
  Informational only: never affects the exit code or `--baseline`.
- **Historical CODATA physical constants**: recognizes older-but-correct
  revisions of physical constants (CODATA 2010/2014/2018), so a codebase
  pinned to an older standard isn't flagged as "truncated" for being
  accurate to its own, older reference value.
- **Context-aware idiomatic suggestions**: `x * 0.017453...` suggests
  `math.radians(x)`, not the bare constant; suggestions are also rewritten
  for the file's existing imports (`from math import pi` renders as `pi`,
  not `math.pi`).
- Constant table roughly tripled: angle conversions, decibels and music
  intervals (including "3 dB"/"6 dB"), statistics (z-scores, the MAD-to-sigma
  factor), CIE Lab color science, astronomy, and exact unit conversions
  (imperial and metric), all mapped to `scipy.constants` where applicable.

### New CLI surface

- `exact identify <number>` - explain a single value directly, no file scan.
- `--fix` - rewrite literals whose exact form is bit-identical (never
  changes program behavior). `--fix-truncated` additionally rewrites
  truncated constants (a real value change, reported as such). `--diff`
  previews either without writing.
- `--changed-only` / `--since REF` - scan only lines changed in git,
  for fast PR checks.
- `--baseline PATH` / `--update-baseline` - snapshot existing findings so a
  legacy codebase can adopt the linter without a big-bang cleanup.
- `--exclude-tests` - skip test files.
- `--jobs N` / `-j N` - parallel scanning across files.
- `--format {text,json,github,sarif}` - GitHub Actions annotations and
  SARIF (for GitHub code scanning) alongside the original text/JSON.
- `[tool.exact]` configuration in `pyproject.toml`, including
  `[tool.exact.constants]` for project-specific named constants.
- `# exact: ignore` inline suppression, with an optional bracketed code list
  (`# exact: ignore[truncated]`) to suppress only specific finding codes.
- `--select`/`--ignore` - every finding now has a stable code (`recognized`,
  `truncated`, `near-miss`, `sequence`); select/ignore filter on it directly,
  the same model ruff and flake8 use. `--truncation-only`/`--near-miss-only`
  still work as sugar for `--select truncated`/`--select near-miss`.
  Configurable via `[tool.exact] select`/`ignore` in `pyproject.toml`.
- **flake8 plugin**: `exact` registers itself under the `flake8.extension`
  entry point automatically on install, prefixed `EXA` (`EXA001` recognized,
  `EXA002` truncated, `EXA003` near-miss). Shares the same `[tool.exact]`
  config, `--select`/`--ignore` composition, and `# exact: ignore[code]`
  suppression as the standalone CLI. Sequence findings are out of scope for
  the plugin - they don't fit flake8's single-location diagnostic model.
- **Near-miss for rationals**: typo detection now also applies to
  repeating-decimal fractions, not just named constants - `0.333331` reads
  as a typo'd `1/3` the same way `2.71827` reads as a typo'd `e`.

### Validated

- **False-positive audit against ordinary code**: six large, non-scientific
  packages (Django, Flask, requests, click, SQLAlchemy, pydantic) scanned in
  full. Five produced zero findings; the one hit (Django's GIS module) is a
  correct recognition of an exact conversion factor, not a bug. See
  `docs/false-positive-audit.md`.
- **Confidence-surplus calibration**: a 42,000-trial Monte Carlo check of the
  confidence formula itself, not just its effects. Empirical false-positive
  rate came in below the formula's own `10**-surplus` prediction at every
  threshold tested. See `docs/confidence-calibration.md` and
  `scripts/calibration_sweep.py` (reproducible, `--quick` mode for a fast
  sanity check).

### Fixed

- A scan-root exclusion bug: scanning a path that happened to live inside a
  `site-packages`/`venv` directory (e.g. an installed package) silently
  excluded everything, because the exclusion list matched *any* path
  component, including ancestors of the scan root itself.
- Short tuples/lists nested inside another container (an RGB triple inside a
  colormap's list of triples) are now correctly treated as data-table
  entries even when the inner tuple alone looks short enough to be "just a
  couple of constants."
- The log-space tier's "no pi term found" check used to assume that meant
  "this is a plain rational in disguise" and bail out - wrong whenever the
  PSLQ coefficient on the literal didn't evenly divide the other exponents,
  which meant a real irrational root of a rational (e.g. a cube root) was
  silently missed.

### Also new

- GitHub Actions CI (Python 3.10-3.14), with the tool self-linting its own
  source as part of the build.
- `.pre-commit-hooks.yaml` for one-line adoption via pre-commit.
- [The corpus study](docs/corpus-study.md): nine popular scientific Python
  packages scanned for real, with three verified upstream precision bugs
  found (sympy, scikit-image, statsmodels) and the false-positive taxonomy
  from everything that looked like a bug but wasn't.

## 0.1.0 (2026-07-06)

Initial release. Table lookup (~140 entries), repeating-decimal rational
detection, and additive PSLQ search, gated by an evidence-surplus confidence
score.
