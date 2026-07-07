# Corpus study: magic floats in popular scientific Python packages

**Date:** 2026-07-07. **Tool:** exact at commit `42f92d9` (table + rational +
additive PSLQ + log-space PSLQ tiers, truncation detection, nested-container
triage). **Method:** installed each package into a clean Python 3.14 venv and ran
`exact <site-packages>/<pkg> --exit-zero -v` against the installed tree. Every
finding class below was verified by reading the package source by hand; nothing
in this document rests on tool output alone.

## Packages scanned

numpy 2.5.1, scipy 1.18.0, matplotlib 3.11.0, sympy 1.14.0, astropy 8.0.1,
statsmodels 0.14.6, Pillow 12.3.0, mpmath 1.3.0, scikit-image 0.26.0.

## Headline numbers

| package | findings | truncated | notes |
|---|---|---|---|
| scipy | 368 | 44 | mostly planted constants in tests |
| mpmath | 177 | 8 | a math library recognizing its own constants; both non-test truncations are intentional (see below) |
| sympy | 117 | 20 | includes the AutoLev deg/rad bug (see below) |
| statsmodels | 105 | 9 | includes the tricube 70/81 truncation (see below) |
| astropy | 86 | 26 | includes exact-conversion truncations; CODATA files correctly recognized but not bugs |
| numpy | 53 | 38 | almost entirely test fixtures |
| matplotlib | 4 | 1 | after the nested-container triage fix; was 1314 before it |
| scikit-image | 1 | 1 | the single survivor is a real bug (Lab 6/29) |
| Pillow | 0 | 0 | few candidate literals at all |
| **total** | **911** | **147** | |

## Verified genuine findings (real code, real precision loss)

1. **sympy** `sympy/parsing/autolev/_listener_autolev_antlr.py:1167,1169` - the
   AutoLev DSL parser hardcodes degree/radian conversion as `0.0174533` and
   `57.2958` (6 significant digits, ~4e-7 relative error) instead of
   `math.pi / 180` and `180 / math.pi`. Production source, not a test. Verified
   present in sympy main as of 2026-07-07. The strongest catch of the study.

2. **scikit-image** `skimage/color/colorconv.py:1224` - the Lab-to-XYZ conversion
   writes the CIE 1976 threshold as `0.2068966`; the standard's exact value is
   **6/29** = 0.20689655172..., so the literal is off by 4.8e-8 (about 9 lost
   digits). A well-known textbook constant, hand-truncated.

3. **statsmodels** `statsmodels/sandbox/nonparametric/kernels.py:572` - the
   Tricube kernel's normalization constant is written as `0.864197530864`; the
   exact value is **70/81**. The adjacent lines in the same class write their
   constants as exact fractions (`175.0/247.0`, `35.0/243.0`), so this literal is
   also a style inconsistency within its own file.

4. **astropy** `astropy/units/imperial.py:51,134` - the US-gallon-to-liter and
   horsepower-to-watt factors are truncated to 9 digits, though both are exactly
   defined conversion values.

## Validation without a bug: the tool agreeing with human comments

Two places where package authors documented the exact form in a comment and the
tool independently derived the same identity:

- **astropy** `astropy/stats/funcs.py:945` writes
  `# NOTE: 1. / scipy.stats.norm.ppf(0.75) = 1.482602218505602` and uses the
  full-precision literal. exact recognized it via its MAD-to-sigma table entry -
  same identity, derived independently. Correct code, correctly recognized.
- **numpy/scipy test suites** plant full-precision `pi`, `e`, `ln(2)` etc. as
  expected values; all recognized at 16-20 digits with large surplus.

## Recognized-but-not-a-bug taxonomy

Categories discovered in this study that are *correct recognitions* but must not
be reported as bugs (several are candidates for future triage heuristics):

1. **Keyboard-mash placeholders.** numpy's random tests use `.123456789`
   everywhere as an arbitrary parameter; it happens to equal 10/81. It is a
   placeholder, not an intended fraction. (~30 of numpy's findings.)
2. **Deliberately versioned historical constants.** astropy ships
   `codata2010.py` through `codata2022.py`; older CODATA revisions have fewer
   published digits by definition. Flagging `codata2010`'s Stefan-Boltzmann
   constant as "truncated" would be wrong - it is a faithful historical record.
3. **Constants that only feed a branch or bound.** mpmath's `gammazeta.py` uses
   `0.577216` (Euler-Mascheroni to 6 digits) solely to pick an integer branch
   index via `floor(...)`, and `libelefun.py` uses `3.3219280948` (log2(10)) to
   estimate a series term count with a `+2` safety margin. Reduced precision is
   intentional and harmless in both.
4. **Data-table entries.** Colormap RGB rows, illuminant coordinate tables, YIQ
   matrix inverses: real rationals, correctly identified, but nobody should
   rewrite a color table as fractions. Now largely handled by the
   nested-container triage rule (see below).

## Bugs this study found in exact itself

The study was as much a test of the tool as of the corpus, and it caught two
real bugs, both fixed with regression tests during the study:

1. **Scan-root exclusion bug** (commit `2448ed9`): `EXCLUDED_DIRS` matched
   ancestors of the scan root, so scanning any installed package under
   `site-packages` silently found nothing. The tell was nine packages "scanning"
   in 0.1 seconds each with zero findings.
2. **Nested-container triage gap** (commit `22d1428`): a 3-element RGB list
   inside a colormap's list-of-lists looked like "a few constants" rather than a
   data table. matplotlib produced 1314 findings before this fix and 4 after -
   all 1310 removed findings were correctly-computed but useless rationals like
   247/255, and all 4 survivors are plausible. scikit-image's illuminant tables
   (6 findings) vanished the same way while its one real bug survived.

Before/after for affected packages: matplotlib 1314 -> 4, scipy 562 -> 368,
sympy 371 -> 117, statsmodels 151 -> 105, astropy 104 -> 86, skimage 7 -> 1.

## A documented miss, and what it motivated

astropy's `cosmology/_src/flrw/base.py` defines
`NEUTRINO_FERMI_DIRAC_CORRECTION: Final = 0.22710731766  # 7/8 (4/11)^4/3` - a
human-documented exact form the tool could not find: the relation is
multiplicative with primes 7 and 11. This directly motivated the log-space PSLQ
tier (commit `42f92d9`), which now catches monomials over {2, 3, 5, pi}; this
specific constant still needs a wider prime basis and remains a tested, known
miss (`test_logspace_known_miss_needs_wider_prime_basis`).

## Reproduction

```
python -m venv venv && venv/bin/pip install exact-linter numpy scipy matplotlib \
    sympy astropy statsmodels pillow mpmath scikit-image
venv/bin/python scripts/corpus_study.py numpy scipy matplotlib sympy astropy \
    statsmodels PIL mpmath skimage
```

Findings drift as the packages release new versions; the numbers above are for
the versions listed at the top.
