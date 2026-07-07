# Confidence-surplus calibration: a Monte Carlo check

**Date:** 2026-07-07. **Method:** `scripts/calibration_sweep.py` (full plan,
42,000 trials, ~5 minutes). Reproducible with `python scripts/
calibration_sweep.py`.

## The claim under test

Every match `exact` reports carries a **surplus**: evidence (the literal's
significant digits) minus cost (the complexity of the claim plus the size of
the space searched to find it). The whole confidence model rests on one
claim: a match reported with surplus S corresponds to roughly a `10**-S`
chance of being a pure coincidence. Every other validation in this project -
the corpus study, the false-positive audit, the rational near-miss check -
tests this indirectly, by seeing whether the tool behaves well on specific
real or random inputs. This is the first check of the formula itself: does
the *rate* actually match what it claims to predict, systematically, across
the full range of surplus values the tool can produce?

## Method

Generated genuinely random d-significant-digit literals (not derived from
any constant, any fraction, or anything meaningful) for d = 6 through 16,
with trial counts scaled down as digit count grows (a 16-digit call costs
~40x a 6-digit call - the log-space tier's PSLQ search dominates at high
precision). Ran each through the real `recognize()` pipeline - every tier,
exactly as a user experiences it - with the confidence gate disabled
(`min_surplus=-100`) so even very weak matches are visible. Every hit is a
coincidence by construction, since the input is pure noise: no random
literal is secretly pi in disguise.

42,000 trials total. 24,366 produced *some* match at the permissive
`min_surplus=-100` threshold - expected and not concerning on its own, since
that setting disables the gate the tool actually ships with; it establishes
the raw "how often does some tier find any candidate fraction/relation at
all" rate, which is exactly what the surplus formula exists to filter.

## Results

| surplus >= | predicted (10^-S) | empirical rate | count / 42,000 |
|---|---|---|---|
| 0 | 1.0 | 1.79e-3 | 75 |
| 1 | 0.1 | 8.10e-4 | 34 |
| 2 (**the default gate**) | 0.01 | 2.62e-4 | 11 |
| 3 | 0.001 | 2.62e-4 | 11 |
| 4 | 1.0e-4 | 2.38e-5 | 1 |
| 5 | 1.0e-5 | 0 | 0 |
| 6-10 | <=1.0e-6 | 0 | 0 |

At every threshold, the empirical rate is *below* the theoretical
prediction - at the default gate (surplus >= 2), by a comfortable ~38x
margin (0.026% observed vs. a 1% theoretical bound). The formula is
conservative, not leaky.

## The marginal hits, examined by hand

Ten hits landed between surplus 1.5 and 4.23 - the ones close enough to the
default gate to be worth reading individually rather than trusting the
aggregate table alone:

```
surplus=4.23  table       0.7797721   = 1/(glaisher)
surplus=3.83  table       0.918939    = ln(2*pi)/2
surplus=3.83  table       0.0157081   = pi/200
surplus=3.23  table       0.618046    = (phi)-1
surplus=3.23  table       0.644937    = (pi**2/6)-1
surplus=3.23  table       0.292892    = 1-(sqrt(2)/2)
surplus=3.23  table       0.0594668   = (2**(1/12))-1
surplus=3.23  table       0.258921    = (10**(1/10))-1
surplus=3.23  table       0.0840306   = 1-(catalan)
surplus=3.23  table       0.648717    = (sqrt(e))-1
surplus=3.00  rational    681.333333  = 2044/3
```

Eight of these ten are **folded** matches (reciprocal, complement `1-x`, or
shift `x+1`/`x-1`), all clustered at 6-7 significant digits. That's worth
noting explicitly rather than glossing over: folding effectively widens the
search space up to 4x, and this is where that cost shows up. But it isn't a
leak - it's the formula working as designed. 8 fold-related hits across
16,000 trials at digits 6-7 is a rate of ~0.05%, and the theoretical
prediction for surplus ~3.2 is `10**-3.2` ~ 0.063%. Those numbers are close
enough that this is exactly what a well-calibrated formula should produce at
that surplus level - not zero, a rare and correctly-priced coincidence.

## Conclusion

The confidence-surplus formula holds up under direct, systematic
measurement, not just argument: empirical false-positive rates are at or
below the theoretical `10**-S` prediction at every tested threshold, for
both the table tier (including all three fold variants) and the rational
tier, across the full practical range of digit counts (6-16). No formula
change was needed as a result of this check - a genuinely clean result,
recorded as such rather than as a lead-in to a fix.

## Reproduction

```
python scripts/calibration_sweep.py          # full run, ~5 minutes
python scripts/calibration_sweep.py --quick  # sanity check, ~10 seconds
```
