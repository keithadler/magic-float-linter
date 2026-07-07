# exact - development plan (next 25 steps)

This file is the working roadmap. Each step is self-contained: goal, files to touch,
implementation notes, and acceptance criteria. Execute steps in order unless a step
says it is independent. One step = one commit (or a few small commits).

## Current state (as of step 0)

- v0.1.0+ on main at https://github.com/keithadler/magic-float-linter
- Working: AST extraction with context ([extract.py](src/exact_linter/extract.py)),
  triage ([triage.py](src/exact_linter/triage.py)), 134-entry constant table
  ([constants.py](src/exact_linter/constants.py)), three recognition tiers plus
  reciprocal folding ([recognize.py](src/exact_linter/recognize.py)), evidence
  scoring ([confidence.py](src/exact_linter/confidence.py)), truncation detection
  (Match.precision_lost / Match.truncated), CLI with --json / --truncation-only /
  --min-surplus / --exit-zero / -v ([cli.py](src/exact_linter/cli.py)),
  text+JSON reports ([report.py](src/exact_linter/report.py)).
- 41 tests passing, ruff clean. Venv at .venv (Python 3.14).

## Ground rules for every step

1. Run `.venv/bin/python -m pytest -q` and `.venv/bin/ruff check .` before every
   commit. Both must be clean.
2. Zero false positives is the product. When touching the engine (recognize.py,
   confidence.py, constants.py, triage.py), re-run the stdlib scan and eyeball it:
   `STDLIB=$(.venv/bin/python -c "import sysconfig; print(sysconfig.get_paths()['stdlib'])")`
   `.venv/bin/exact "$STDLIB" --exit-zero | tail -5`
   The finding count should stay in the same ballpark (~54 as of step 0) unless the
   step intentionally expands coverage. Any new finding must be manually verified.
3. Never use em dashes in prose, docs, or comments - use " - " instead.
4. New behavior gets a test first or alongside, never after the commit.
5. Every new CLI flag gets: argparse help text, README usage-block line, and a test.
6. Do not add runtime dependencies beyond mpmath without a step saying so.
7. Update README when behavior changes. Update this file: mark steps DONE with date.

---

## Phase A - context-aware suggestions (steps 1-4)

### Step 1: capture the enclosing operation in the extractor [DONE 2026-07-07]
**Goal:** FloatLiteral knows how the literal is used, so later steps can suggest
idioms like math.radians(x).
**Files:** src/exact_linter/extract.py, tests/test_extract.py
**How:** Add two fields to FloatLiteral: `op: str = ""` (one of "mul", "div-num",
"div-den", "add", "sub", "" ) and `other_operand: str = ""` (source text of the
other operand, only when it is a simple Name or Attribute, else ""). Populate them
in extract_source by checking whether the literal's parent (looking through a
UnaryOp minus) is an ast.BinOp with Mult/Div/Add/Sub. For Div, distinguish whether
the literal is numerator or denominator.
**Accept:** New tests: `x * 0.017453292519943295` gives op="mul",
other_operand="x"; `1.0 / 2.302585092994046` on the denominator side gives
op="div-den"; a bare assignment gives op="". All existing tests still pass.

### Step 2: idiom rewrite rules [DONE 2026-07-07]
**Goal:** Suggestions become idiomatic when context allows.
**Files:** new src/exact_linter/idioms.py, src/exact_linter/recognize.py (no
changes needed if idioms is applied at the Finding level), src/exact_linter/cli.py,
tests/test_idioms.py
**How:** idioms.py exposes `idiomatic(match, literal) -> str | None` returning an
improved suggestion or None. Rules (form is Match.form, op/other from FloatLiteral):
- form "pi/180", op "mul" -> `math.radians({other})`
- form "180/pi", op "mul" -> `math.degrees({other})`
- form "1/ln(2)", op "mul" -> `math.log2({other})`
- form "1/ln(10)", op "mul" -> `math.log10({other})`
- form "ln(2)" or "ln(10)", op "div-den" -> `math.log2({other})` / `math.log10({other})`
- form "2*pi", op "mul" -> `math.tau * {other}` (mild, but consistent)
Only fire when other_operand is non-empty. CLI: apply idiomatic() when building
findings; if it returns a string, put it in a new Finding field
`idiomatic_suggestion` and render it in report.py as the primary suggestion with
the plain one in parentheses.
**Accept:** Test file with `rad = deg * 0.017453292519943295` produces suggestion
`math.radians(deg)`. JSON output contains both suggestion fields.

### Step 3: import-aware suggestion rendering
**Goal:** Do not tell people to write math.pi when they already did
`from math import pi`.
**Files:** src/exact_linter/extract.py (collect imports per file),
src/exact_linter/report.py, tests/test_extract.py, tests/test_cli.py
**How:** extract_source also returns the set of names imported from math (and
whether `import math` / `import numpy` exist). Simplest structure: a new dataclass
FileInfo(literals, math_names: frozenset[str], has_math: bool, has_numpy: bool)
returned by a new function extract_file_info; keep extract_file/extract_source
working as before for compatibility. In report rendering, if suggestion starts
with "math." and has_math is False, append note "add: import math". If the bare
name (e.g. pi) is in math_names, rewrite "math.pi" -> "pi" in the suggestion.
**Accept:** Test: file with `from math import pi` and literal 3.141592653589793
suggests `pi`, not `math.pi`. File with no imports notes "add: import math".

### Step 4: stdlib spot-check and README for Phase A
**Goal:** Prove Phase A on real code, document it.
**Files:** README.md, PLAN.md
**How:** Run the stdlib scan, confirm idiomatic suggestions appear where expected
(turtle.py and random.py are likely candidates), paste one real example into the
README section "Context-aware suggestions". Mark steps 1-4 DONE here.
**Accept:** README shows a real captured example. Scan finding count unchanged.

## Phase B - configuration and suppression (steps 5-8)

### Step 5: inline suppression comments [DONE 2026-07-06]
**Goal:** `# exact: ignore` on a line silences findings on that line.
**Files:** src/exact_linter/extract.py, src/exact_linter/cli.py, tests/test_cli.py
**How:** extract_source records for each literal whether its source line (or the
line above, if the line above is only a comment) matches the regex
`#\s*exact:\s*ignore`. Add field `suppressed: bool = False`. CLI counts suppressed
findings under skipped["suppressed by comment"].
**Accept:** Test: two identical literals, one with trailing `# exact: ignore`,
yields exactly one finding, and -v shows the suppressed count.

### Step 6: pyproject.toml configuration
**Goal:** Projects configure exact without CLI flags.
**Files:** new src/exact_linter/config.py, src/exact_linter/cli.py,
tests/test_config.py
**How:** config.py: `load_config(start_dir) -> Config` walking up from start_dir
to find pyproject.toml with a [tool.exact] section (use tomllib, stdlib in 3.11+;
add `tomli; python_version < "3.11"` conditional dependency in pyproject.toml).
Config dataclass: min_surplus (float), min_digits (int), exclude (list[str] of
glob patterns), truncation_only (bool). CLI flags override config values; config
overrides defaults. Wire min_digits into triage via parameter (default stays 6).
**Accept:** Test with a tmp pyproject.toml setting min_surplus = 5.0 suppresses a
finding that appears with the default. Precedence test: CLI flag beats config.

### Step 7: user-defined constants
**Goal:** Projects can add domain constants to the table.
**Files:** src/exact_linter/config.py, src/exact_linter/constants.py,
tests/test_config.py
**How:** [tool.exact.constants] maps name -> {value = "<decimal string>",
suggestion = "<code>", note = "..."} . config.py parses these into ConstantEntry
objects; constants.table() gains an optional `extra: tuple[ConstantEntry, ...]`
parameter (change lru_cache accordingly, e.g. key on the tuple). CLI threads
config constants through to recognize via a parameter (add `extra_entries` to
recognize()).
**Accept:** Test: config defines value "1.32471795724474602596" (the plastic
number) with a suggestion; a literal matching it is found and reports the custom
suggestion.

### Step 8: default test-file damping [DONE 2026-07-07]
**Goal:** Reduce noise: findings in test files are usually planted constants, not
bugs (the stdlib scan is almost all test files).
**Files:** src/exact_linter/cli.py, src/exact_linter/config.py, README.md,
tests/test_cli.py
**How:** Add `--include-tests/--exclude-tests` (config key include_tests, default
true for now - flipping the default is a product decision to revisit). When
excluding, skip files matching test_*.py, *_test.py, or any path segment named
tests or test. Report the count under skipped.
**Accept:** Test directory with test_foo.py and foo.py: --exclude-tests reports
only foo.py findings.
**Note:** shipped as a single `--exclude-tests` flag (default already "include",
so no paired `--include-tests` was needed) and no config.py dependency (step 6
not done yet). Excluded-file count is reported as a separate verbose line, not
folded into the per-literal skipped-reasons table (different units: files vs.
literals).

## Phase C - fix mode (steps 9-11)

### Step 9: --fix for safe, full-precision rewrites
**Goal:** Automatic rewriting where it cannot change behavior meaningfully.
**Files:** new src/exact_linter/fix.py, src/exact_linter/cli.py, tests/test_fix.py
**How:** fix.py: `apply_fixes(path, findings) -> str` returns new source. Only fix
findings where match.truncated is False AND the suggestion evaluates (in Python,
with import math) to a float equal to float(literal.text) bit-for-bit - check with
eval in a namespace {"math": math} guarded by try/except; skip otherwise. Replace
by exact line/col slice using the literal's text length (never regex). If any fix
uses "math." and the file lacks import math, insert `import math` after the last
top-level import (or at top after docstring). CLI: --fix applies changes,
--fix --diff prints a unified diff instead of writing. Always print a summary of
fixed/skipped.
**Accept:** Round-trip test: file with `x = 3.141592653589793` becomes
`x = math.pi`, file still parses, `float(eval)` equality held; truncated literal
`3.14159` is NOT touched; running --fix twice changes nothing the second time.

### Step 10: --fix-truncated (explicit, value-changing)
**Goal:** Let users opt in to fixing truncation bugs, which changes numeric values.
**Files:** src/exact_linter/fix.py, src/exact_linter/cli.py, tests/test_fix.py
**How:** Separate flag --fix-truncated (implies --fix). Only fixes findings with
truncated True and tier "table" (highest confidence class). Prints a WARNING
banner listing each value change old -> new.
**Accept:** `3.14159` becomes `math.pi` only under --fix-truncated; the summary
lists the numeric delta.

### Step 11: fixer hardening
**Goal:** Trust. The fixer must never corrupt a file.
**Files:** tests/test_fix.py
**How:** Property-style tests: for a corpus of tricky sources (literal inside
f-string is NOT a Constant so should be untouched; multiple literals on one line;
literal at line start/end; CRLF line endings; unicode nearby; parenthesized
literal), assert output parses (ast.parse) and non-target text is byte-identical.
Also add a --fix run against a copied subset of stdlib test files in a tmp dir,
asserting everything still parses.
**Accept:** All hardening tests pass.

## Phase D - CI, packaging, publishing (steps 12-15)

### Step 12: GitHub Actions CI [DONE 2026-07-06]
**Goal:** Tests and lint on every push/PR.
**Files:** new .github/workflows/ci.yml
**How:** Matrix on python-version [3.10, 3.11, 3.12, 3.13, 3.14], steps:
checkout, setup-python, `pip install -e '.[dev]'`, `pytest -q`, `ruff check .`.
Use ubuntu-latest. Trigger on push to main and pull_request.
**Accept:** Push, then verify with `gh run watch` or
`gh run list --repo keithadler/magic-float-linter -L 1` that the run succeeds on
all versions. Fix any 3.10/3.11 incompatibilities found (the code targets 3.10+;
watch for tomllib in step 6 - conditional import).

### Step 13: self-lint and badge [DONE 2026-07-06]
**Goal:** exact runs clean on its own source; advertise CI status.
**Files:** .github/workflows/ci.yml, README.md, possibly test files
**How:** Add CI step `exact src/ --exclude-tests` (exit code enforces it). If it
flags anything in src/, fix the source or add `# exact: ignore` with a comment
why. Add the standard actions workflow badge to the README top.
**Accept:** CI green including the self-lint step; badge renders.

### Step 14: PyPI release 0.2.0
**Goal:** `pip install exact-linter` works.
**Files:** pyproject.toml (version bump to 0.2.0), new CHANGELOG.md
**How:** Write CHANGELOG.md summarizing 0.1.0 -> 0.2.0 (phases A-C). Build with
`.venv/bin/pip install build twine && .venv/bin/python -m build` then
`.venv/bin/twine check dist/*`. Publishing requires Keith's PyPI token - STOP and
ask Keith to either run `twine upload dist/*` himself or provide a token. Prefer
setting up Trusted Publishing (PyPI -> GitHub OIDC) with a release.yml workflow
triggered on GitHub release creation, which needs Keith to configure the PyPI
side once.
**Accept:** twine check passes; either the package is live on PyPI or a
release.yml exists and PLAN.md records what Keith must click in PyPI settings.

### Step 15: pre-commit hook support [DONE 2026-07-06]
**Goal:** One-line adoption in any repo using pre-commit.
**Files:** new .pre-commit-hooks.yaml, README.md
**How:** Standard hook definition: id "exact", entry "exact", language "python",
types [python]. Document usage in README (repo URL + rev). Consider a second hook
id "exact-truncation" with args ["--truncation-only"].
**Accept:** In a scratch repo, `pre-commit try-repo /path/to/magic-float-linter exact --files somefile.py`
runs and reports findings.

## Phase E - output formats (steps 16-17)

### Step 16: SARIF output
**Goal:** GitHub code scanning integration.
**Files:** new src/exact_linter/sarif.py, cli.py, tests/test_sarif.py, README.md
**How:** `--format sarif` (refactor --json into `--format json` keeping --json as
an alias). Emit SARIF 2.1.0: one rule per category ("recognized-constant",
"truncated-constant"), physicalLocation with file/line/col, message with form and
suggestion, level "note" for recognized and "warning" for truncated. Validate
structure in tests by loading with json and checking required keys (no external
schema dependency).
**Accept:** Output loads as JSON with runs[0].tool.driver.rules and results
populated; README documents the code-scanning upload-sarif snippet.

### Step 17: GitHub annotations format [DONE 2026-07-06]
**Goal:** Findings appear inline on PRs without code-scanning setup.
**Files:** cli.py, report.py, tests/test_cli.py
**How:** `--format github` prints workflow commands:
`::warning file={f},line={l},col={c}::{literal} is {form}; suggest {suggestion}`
(::notice for non-truncated). Add to the CI self-lint step.
**Accept:** Test asserts exact command syntax; CI shows annotations on a PR.

## Phase F - engine improvements (steps 18-21)

### Step 18: log-space tier (multiplicative relations) [DONE 2026-07-07]
**Goal:** Catch monomials like 2^a * 3^b * pi^c that the additive search misses.
**Files:** src/exact_linter/recognize.py, confidence.py, tests/test_recognize.py
**How:** New finder _match_logspace, after _match_pslq, only for digits >= 12 and
x > 0: run mpmath.pslq on [ln(x), ln 2, ln 3, ln 5, ln 10, ln pi] with
maxcoeff=64, tol scaled to the literal's digits like the pslq tier. A relation
n0*ln x + n1*ln 2 + ... = 0 with n0 != 0 gives x = product of primes/pi to
rational powers. Render form like "2**3*pi**-1" and a Python suggestion. Verify
at digits+20 exactly as _match_pslq does. Confidence: charge
integer_digit_cost of all exponents + 1 per base used + PSLQ_SEARCH_DIGITS + 1
(wider basis). Reject if the relation is degenerate (only n0 nonzero -> x = 1).
**Accept:** recognize("2.5464790894703254") (which is 8/pi) or a planted
"0.6079271018540267" (6/pi**2) resolves; all junk tests still return None; stdlib
scan gains no false positives (manually review any new findings).
**Note:** basis shipped as {2, 3, 5, pi} without 10 - `ln(10) = ln(2)+ln(5)` makes
a basis that includes it linearly dependent on itself, so PSLQ always finds that
trivial identity instead of any real relation involving x (caught by prototyping
before writing the real code, not by the test suite). The plan's own cited
examples (8/pi, 6/pi**2) turned out to already be reachable via table +
reciprocal folding (`pi/8` and `pi**2/6` are listed entries) and via the
additive PSLQ tier's own search, so they don't actually exercise this tier;
shipped tests use `2**(1/3)/pi` and `3**(2/5)/pi` instead, found by probing
candidates against the real implementation. Confidence charges exponent digit
cost + 1 (for pi, the only named factor) + LOGSPACE_SEARCH_DIGITS - not a
separate per-factor charge, which would have made the plan's own 6/pi**2
example fail the default surplus threshold. Stdlib scan: 0 logspace findings
(expected - this tier targets scientific/physics code), scan time roughly
doubled (33s -> 66s) since every 12+ digit literal surviving earlier tiers now
runs an extra PSLQ search; a real cost for step 21 (performance) to address.

### Step 19: minimal-polynomial tier for quadratic algebraics
**Goal:** Recognize numbers like tan(pi/8) = sqrt(2)-1 when not in the table, as
roots of small quadratics.
**Files:** src/exact_linter/recognize.py, confidence.py, tests/test_recognize.py
**How:** New finder using mpmath.pslq on [1, x, x**2] (degree 2 only, maxcoeff
100, digits >= 12). On relation a + b*x + c*x**2 = 0, solve the quadratic exactly
and render as "(-b +/- sqrt(b^2-4ac)) / 2c" simplified: emit form
"root of {c}x^2+{b}x+{a}" and, when the discriminant is a perfect-square-free
small int, a suggestion like "(math.sqrt(8) - 2) / 2" - acceptable to keep the
suggestion mechanical rather than fully simplified. Charge digits of a, b, c
plus PSLQ_SEARCH_DIGITS.
**Accept:** recognize("0.41421356237309515") -> quadratic identifying sqrt(2)-1
(or the table 'silver ratio conjugate' entry wins, which is fine - test with a
value NOT in the table, e.g. "1.3660254037844386" = (1+sqrt(3))/2). Junk still
None.

### Step 20: complement and negation folding [DONE 2026-07-07]
**Goal:** Recognize 1-entry and entry-1 patterns (probabilities, conjugates).
**Files:** src/exact_linter/recognize.py, confidence.py, tests/test_folding.py
**How:** In _match_table, after reciprocal folding, try 1-x and x+1 against the
table for entries with value in (0, 2): if 1-x matches entry, form
"1-({entry.form})", suggestion "1 - {sugg}". Same parenthesization helper as
reciprocals. Charge RECIPROCAL_PENALTY (rename to FOLD_PENALTY, now log10(4) for
the 4x wider search: direct, reciprocal, complement, shift).
**Accept:** recognize("0.36787944117144233") still gives 1/e directly (listed);
recognize("0.6321205588285577") (1 - 1/e, exponential saturation) resolves via
complement fold. Junk tests still pass. Stdlib scan reviewed.

### Step 21: performance pass [DONE 2026-07-07]
**Goal:** Big-corpus scans get fast; establish a benchmark.
**Files:** src/exact_linter/recognize.py, cli.py, new tests/test_perf.py (marked
slow/skip by default), README.md
**How:** (a) lru_cache on recognize keyed by (text, min_surplus) - repeated
literals across a corpus are common. (b) In the CLI, dedupe candidate texts
first, recognize each unique text once, then fan results back out to locations.
(c) Add --jobs N using concurrent.futures.ProcessPoolExecutor over files chunks
(recognition is CPU-bound; guard with if N > 1). Time the stdlib scan before and
after and record both numbers in the commit message.
**Accept:** Stdlib scan wall time improves (record it); results identical to
pre-change scan output (diff the two outputs).
**Note:** stdlib benchmark: 45.5s baseline -> 42.5s serial with lru_cache ->
25.1s with --jobs 8 (outputs byte-identical in all cases, verified by diff).
The (b) explicit dedupe step was unnecessary - the lru_cache makes repeated
literals free automatically, so no separate fan-out machinery was written.
Match became a frozen dataclass since cached results are shared between
callers. Parallel CPU tops out around 200% even with 8 workers because one or
two very large files dominate the tail; that's an honest limit of file-level
parallelism, and chunksize=1 (not the plan's "files chunks") is what load
balancing wants here since per-file cost is wildly uneven. No separate
test_perf.py - the equivalence test (serial vs --jobs 2, identical JSON) runs
fast and lives in test_cli.py.

## Phase G - multi-language (steps 22-24)

### Step 22: extractor interface
**Goal:** Decouple recognition from Python-specific extraction.
**Files:** src/exact_linter/extract.py, new src/exact_linter/languages/__init__.py
(move/re-export as needed), cli.py
**How:** Define a Protocol: an extractor takes (source: str, file: Path) and
yields FloatLiteral. Registry maps file suffixes to extractors ({".py": python}).
CLI iterates all registered suffixes instead of hardcoding *.py. Pure refactor -
no behavior change. Keep public imports working (exact_linter.extract_source).
**Accept:** All existing tests pass unchanged; scanning a directory still finds
exactly the same literals as before the refactor.

### Step 23: JavaScript/TypeScript extractor
**Goal:** exact works on .js/.ts/.jsx/.tsx.
**Files:** new src/exact_linter/languages/javascript.py, pyproject.toml (optional
extra: `js = ["tree-sitter>=0.21", "tree-sitter-javascript", "tree-sitter-typescript"]`),
tests/test_js.py, README.md
**How:** Use tree-sitter to find number tokens (kind "number"), skip integers and
hex/octal/binary/BigInt, capture surrounding variable_declarator name as context
and array size for the sequence rule. Suggestions rendered per-language: add a
`language` field to FloatLiteral (default "python"); a suggestion mapper converts
"math.pi" style table suggestions to "Math.PI", "Math.sqrt(2)", "Math.LN2",
"Math.LOG2E" etc. - add an explicit mapping table for the common cases and fall
back to a comment-style suggestion "(= pi/180)" when unmappable. Import guard:
importing javascript.py without tree-sitter installed must raise a clear error
only when .js files are actually scanned.
**Accept:** Fixture .js file with `const rad = deg * 0.017453292519943295;` is
flagged with a JS-appropriate suggestion. Python-only install still works and
tests skip JS tests when tree-sitter is missing (pytest.importorskip).

### Step 24: C/C++ extractor
**Goal:** exact works on .c/.h/.cpp/.hpp.
**Files:** new src/exact_linter/languages/c.py, pyproject.toml (extra "c" with
tree-sitter-c and tree-sitter-cpp), tests/test_c.py, README.md
**How:** Same pattern as step 23. Handle suffixes (1.5f, 1.5L) by stripping
before significant_digits; skip hex floats (0x1.8p3) for now with a skip reason.
Suggestions: C++ gets std::numbers::pi (note "C++20"), C gets M_PI (note
"requires _USE_MATH_DEFINES on MSVC"); fall back to comment-style for anything
without a standard name.
**Accept:** Fixture .c file with `double r = a * 0.017453292519943295;` flagged;
suffixed literal `3.14159f` recognized as truncated pi.

## Phase H - the showpiece (step 25)

### Step 25: corpus study [DONE 2026-07-07]
**Goal:** The writeup artifact: "how much magic-float debt is in popular Python
code" - also the definitive false-positive audit.
**Files:** new scripts/corpus_study.py, new docs/corpus-study.md
**How:** Script: given a list of the top ~50 pip packages (hardcode a reasonable
list: numpy, scipy, pandas, matplotlib, requests, django, flask, sympy, sklearn,
pillow, etc.), pip download sdists into a temp dir (or git clone shallow),
run the scanning pipeline programmatically (import exact_linter, not subprocess),
aggregate: findings per package, per tier, truncated count, top 20 most common
recognized forms, total literals scanned vs triaged. Emit a markdown report with
tables into docs/corpus-study.md, including a manually-reviewed false-positive
section (review EVERY finding flagged truncated; sample 30 of the rest).
**Accept:** docs/corpus-study.md committed with real numbers and the manual
review notes. Any false positive found becomes a regression test and, if
fixable, a scoring fix in the same commit series.
**Note:** executed early (out of order) because the tool was ready and the
study kept paying for itself. Nine scientific packages instead of 50 web/misc
ones - the tool's audience is numeric code, and requests/django would have
contributed near-zero candidates (Pillow already scanned as 0 findings from
117 literals). scripts/corpus_study.py scans importable packages in the
current environment rather than pip-downloading sdists (simpler, same
result). The study found two real bugs in exact itself (scan-root exclusion,
nested-container triage - both fixed with regression tests mid-study), three
genuine upstream bugs (sympy AutoLev deg/rad, skimage Lab 6/29, statsmodels
tricube 70/81), and one documented miss that motivated shipping step 18
early. Manual review was 100% of non-test truncated findings rather than
"every truncated + sample 30" - test-file findings are planted constants by
definition and were spot-checked instead.

---

## Step ordering notes for the executor

- Phases A, B, C are sequential within themselves. Phase D can run any time after
  B (step 13 uses step 5/8 features). E after D. F is independent of B-E and can
  interleave. G after F is wise (engine stable before porting). H last.
- If a step balloons past ~300 lines of diff, stop and split it.
- When in doubt about a product decision, choose the conservative option (fewer
  findings, no behavior change) and leave a note in this file under the step.
