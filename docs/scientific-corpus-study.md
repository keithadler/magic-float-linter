# Corpus study: magic floats in scientific and numerical Python packages

**Date:** 2026-07-07. **Tool:** exact at commit `c802b3e`. **Method:** installed
~100 scientific, numerical, and domain packages (astronomy, physics, chemistry,
signal/image processing, geospatial, quantitative finance, numerical methods)
into clean venvs and ran `exact <pkg> --exclude-tests` against each. Every
truncation and near-miss below was read by hand in context. This is the
counterpart to [the 100 non-scientific packages](false-positive-audit-100.md):
this is the code where hand-typed constants actually live, so this is where the
tool is supposed to earn its keep - and where its limits show.

## Headline

Scanning the domain the tool was built for lights it up - hundreds of
recognitions across the corpus. But the honest signal is in the triage, not the
raw count. Reading every truncation in context, the findings fall into a small
number of buckets, and only one of them is "a bug worth fixing."

**The one recurring genuine bug: a hand-typed, truncated pi.** A bare
`3.14159` / `3.141592` standing in for `math.pi`/`np.pi` shows up, independently,
in several widely-used libraries:

| Library | Literal | Where | Filed |
|---|---|---|---|
| **pymatgen** | `3.14159` | `io/vasp/outputs.py` optical absorption coefficient (same file uses `np.pi` elsewhere) | [pymatgen-core#89](https://github.com/materialsproject/pymatgen-core/issues/89) |
| **pandas-ta** | `3.14159` (x4) | Ehlers indicators (`ssf`, `ssf3`, `reflex`, `trendflex`) as a default param; `sqrt2` defaulted to `1.414` | - |
| **imgaug** | `3.141592` (x2) | `augmenters/geometric.py` | - |
| **sympy** | `0.0174533` (= pi/180) | AutoLev parser | [sympy#30063](https://github.com/sympy/sympy/issues/30063) |

Across everything scanned this project, **"someone typed a short pi instead of
`math.pi`" is the single most common genuine instance of this bug class.**

Other genuine (but low-impact) truncations of named constants:

- **kornia** - the CIE Lab threshold `6/29` written as `0.2068966` (the *same*
  truncation independently confirmed in scikit-image), and `1/sqrt(2)` as
  `0.70710678` in a Gaussian window (the exact form is even left commented out
  right below it).
- **metpy** - `sqrt(2)` as `1.4142135` in a skew-T plot.
- Rounded unit-conversion factors (BTU, horsepower, lb/kg, parsec) in
  `fluids`, `chemicals`, `numericalunits`, `unyt`, `rebound` - real truncations,
  but of conversion constants where the rounding is immaterial.

## What looked like bugs but is not (the majority)

Reading context disqualified most of the raw truncations. They cluster into
three systematic categories - and two of them are really findings about *the
tool*, not the libraries:

1. **Coefficients of standard fitted approximations.** Fixing one term in
   isolation would *break* the fit:
   - **kornia** `0.39894228` (x2) is the leading term of the Abramowitz & Stegun
     modified-Bessel polynomial approximation (comment: "Adapted from MONAI") -
     not an independent `1/sqrt(2*pi)`.
   - **cvxpy** `0.577216` (Euler-Mascheroni), `0.422784` (1 - gamma), and
     `0.918939` (ln(2*pi)/2) are intercepts of a *piecewise-linear convex lower
     bound* on log-gamma in `loggamma.py`, deliberately low precision.
   - **fluids** `1.74533E-2` (= pi/180) is inside a port of the reference
     NRLMSISE-00 atmosphere model - faithful-to-standard, like SGP4.
   - **biopython** `1/360`, `1/1260`, `1/1680` are Stirling-series coefficients
     in a chi-square routine.
2. **Older-but-correct reference values.** Not truncations of the current value,
   but the exact value of an earlier standard:
   - **ase** `6.67428e-11` (G) sits literally inside a dict labeled
     `'2006':  # CODATA 2006`.
   - **thermo** `8.31451` / `8.31448` (R) are per-fluid equation-of-state
     reference values - you must use the same R the EOS was fit with.
   - **quantities** ships a full CODATA table (G, 1/c, and more) with explicit
     `precision` fields.
3. **Coincidental rationals in tabulated / fitted statistical data.**
   - **arch** `-18.44444` is a Phillips-Ouliaris cointegration *critical value*
     (a Monte-Carlo output), not the rational -166/9.
   - **pmdarima** `65.44445` is a fitted seasonality threshold, not 589/9.
   - **biopython** `0.333333333` values are `sleep()` throttles in REST code, not
     mathematical constants.

## Near-miss (typo) detection: 3 false positives, all explained

Every near-miss the tool flagged in this corpus turned out to be a *measured
physical quantity that happens to land near a mathematical constant* - a genuine
weakness of near-miss detection on constant-dense scientific data:

- **fluids** `0.0123456789` - an arbitrary "close-to-zero split-point" in a
  root-finder (the code comment says so), not a typo of `1/81`.
- **molmass** `0.618049` - Lithium's measured electron affinity, coincidentally
  near `phi - 1`.
- **quantities** `5.94592e-2` - the measured muon-tau mass ratio, coincidentally
  near the semitone ratio `2**(1/12) - 1`.

## What this study establishes

Two things, honestly:

1. **The tool finds real, recurring truncations in major scientific libraries** -
   and two of them (sympy, pymatgen) were filed upstream as issues. But even in
   its home domain, *genuine* truncated constants are a minority of raw findings,
   and *consequential* ones rarer still. The bug is common; the bug mattering is
   rare.
2. **The scan exposed two false-positive sources worth fixing in the tool
   itself** (both currently listed as limitations, not yet addressed): it flags
   (a) older CODATA revisions it doesn't have registered, and (b) individual
   coefficients of standard fitted approximations (Abramowitz & Stegun, Lanczos,
   piecewise-linear convex relaxations), as "truncated." A user scanning
   physics/ML code will hit these and has to recognize them by context.

## Reproduction

```
python -m venv venv
venv/bin/pip install exact-linter
venv/bin/pip install pymatgen kornia metpy imgaug pandas-ta ase thermo \
    quantities fluids chemicals cvxpy biopython   # etc.
venv/bin/exact venv/lib/python3.*/site-packages/<pkg> --exclude-tests --exit-zero
```

Some packages (across the audio/signal/finance set especially) may not resolve
on the newest Python; a slightly older interpreter has better scientific-wheel
coverage. Findings drift with new releases; the specifics above are current as
of the study date.
