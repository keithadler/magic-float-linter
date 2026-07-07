"""Monte Carlo calibration check for the confidence-surplus formula.

Claim under test: a match reported with surplus S corresponds to roughly a
10**-S chance of being a coincidence. This generates genuinely random
d-significant-digit literals (not derived from any constant), runs the real
recognize() pipeline - every tier, exactly as a user experiences it - with
the confidence gate disabled (min_surplus=-100), and records how often, and
at what reported surplus, it finds "something" anyway. Every hit here is a
coincidence by construction, since the input is pure noise.

Usage: python scripts/calibration_sweep.py [--quick]

See docs/confidence-calibration.md for the full write-up of a real run
(42,000 trials, ~5 minutes). --quick runs a much smaller sweep (~30s) for a
sanity check rather than a publishable result.
"""

from __future__ import annotations

import random
import sys
import time
from collections import Counter

from exact_linter.recognize import recognize

random.seed(20260707)

# trial counts scaled down as per-call cost grows: a 16-digit call is ~40x a
# 6-digit call, dominated by the log-space tier's PSLQ search at high precision
FULL_PLAN = [
    (6, 8000), (7, 8000), (8, 6000), (9, 5000), (10, 4000),
    (11, 3000), (12, 2500), (13, 2000), (14, 1500), (15, 1200), (16, 800),
]
QUICK_PLAN = [(d, max(50, n // 40)) for d, n in FULL_PLAN]

THRESHOLDS = [0, 1, 2, 3, 4, 5, 6, 8, 10]


def rand_literal(digits: int) -> str:
    mantissa = random.randint(10 ** (digits - 1), 10**digits - 1)
    # vary the decimal point position - real code's magic-float candidates
    # span a wide range of magnitudes, not just "0.xxxxx"
    shift = random.randint(-2, 3)
    if shift <= 0:
        return f"0.{'0' * -shift}{mantissa}"
    s = str(mantissa)
    if shift >= len(s):
        return f"{mantissa}{'0' * (shift - len(s) + 1)}.0"
    return f"{s[:shift]}.{s[shift:]}"


def main() -> None:
    plan = QUICK_PLAN if "--quick" in sys.argv else FULL_PLAN
    results = []
    t_start = time.perf_counter()
    for digits, n in plan:
        hits = []
        for _ in range(n):
            text = rand_literal(digits)
            m = recognize(text, min_surplus=-100.0)
            if m is not None:
                hits.append({"text": text, "tier": m.tier, "surplus": m.surplus, "form": m.form})
        results.append({"digits": digits, "trials": n, "hits": hits})
        elapsed = time.perf_counter() - t_start
        print(
            f"digits={digits:2d}  trials={n:5d}  hits={len(hits):4d}  elapsed={elapsed:6.1f}s",
            flush=True,
        )

    total_trials = sum(r["trials"] for r in results)
    all_hits = [h for r in results for h in r["hits"]]

    print()
    print(f"total trials: {total_trials}, total hits (any surplus, incl. negative): {len(all_hits)}")
    print()
    print(f"{'surplus >=':>10} | {'predicted 10^-S':>16} | {'empirical rate':>16} | {'count':>8} | verdict")
    for s in THRESHOLDS:
        count = sum(1 for h in all_hits if h["surplus"] >= s)
        empirical = count / total_trials
        predicted = 10**-s
        verdict = "OK (conservative)" if empirical <= predicted * 3 or count == 0 else "CHECK - leaky?"
        print(f"{s:>10} | {predicted:>16.2e} | {empirical:>16.2e} | {count:>8} | {verdict}")

    print()
    tier_counts = Counter(h["tier"] for h in all_hits if h["surplus"] >= 0)
    print("tier breakdown of hits with surplus >= 0:", dict(tier_counts))


if __name__ == "__main__":
    main()
