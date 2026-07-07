# Corpus study: magic floats in popular AI/ML Python packages

**Date:** 2026-07-07. **Tool:** exact at commit `cae048a` (table + rational +
additive PSLQ + log-space PSLQ tiers, truncation detection, near-miss
detection, nested-container triage, whole-sequence recognition). **Method:**
installed each package into a clean Python 3.14 venv (CPU-only wheels) and ran
`exact <site-packages>/<pkg> --exclude-tests --exit-zero` against the
installed tree. Every finding below was verified by reading the package
source by hand, and the two real findings were independently confirmed
present on each project's live GitHub `main` branch on the study date -
nothing here rests on tool output alone.

## Packages scanned

torch 2.12.1, transformers 5.13.0, jax 0.10.2, jaxlib 0.10.2, xgboost 3.3.0,
lightgbm 4.6.0, keras 3.15.0 (torch backend), onnx 1.22.0.

## Headline numbers

| package | float literals | findings | truncated | verdict |
|---|---|---|---|---|
| jax | 12,421 | 56 | 8 | all 8 truncations are frozen backward-compat test snapshots, not bugs |
| torch | 5,902 | 27 | 0 | clean - every recognized constant is full double precision |
| transformers | 12,998 | 11 | 11 | **real bug, 8 locations** (see below) |
| xgboost | 480 | 11 | 0 | all in test fixture data, coincidental rationals |
| onnx | 7,172 | 1 | 1 | **real bug, 1 location** (see below) |
| lightgbm | 67 | 0 | 0 | clean |
| keras | 1,821 | 0 | 0 | clean |
| jaxlib | 0 | 0 | 0 | no Python source (native extension) |

## Verified genuine findings (real code, real precision loss)

1. **transformers** - `1.442695041` appears hardcoded in eight places across
   the TimesFM and VideoPrism model implementations, in both the generated
   `modeling_*.py` files and their `modular_*.py` sources:

   - `models/timesfm/modeling_timesfm.py:232`
   - `models/timesfm/modular_timesfm.py:189`
   - `models/timesfm2_5/modeling_timesfm2_5.py:324`
   - `models/timesfm2_5/modular_timesfm2_5.py:202`
   - `models/videoprism/modeling_videoprism.py:589` (`_R_SOFTPLUS_0`)
   - `models/videoprism/modular_videoprism.py:50` (`_R_SOFTPLUS_0`)

   The exact value is **1/ln(2) = 1.4426950408889634**; the hardcoded literal
   is a correctly-rounded 10-digit truncation, about 6 digits short of a
   double. It is not a stray test value - it feeds directly into the
   attention scale factor:

   ```python
   scale = F.softplus(self.scaling).mul(1.442695041 / math.sqrt(self.head_dim))
   ```

   Confirmed still present on `huggingface/transformers` `main` as of
   2026-07-07 (not something already fixed upstream).

   **Practical impact is genuinely negligible, and that's worth saying
   plainly:** the relative error introduced is about 6e-10, roughly five
   orders of magnitude below float32's own precision (~1.2e-7), the dtype
   these models actually run in. Correcting it would not measurably change
   any model's output. It also is not free the way the sympy fix was -
   TimesFM's `self.scaling` is a *trained* parameter multiplied by this
   constant at inference time, so in principle a pretrained checkpoint was
   fit with this exact (truncated) scale baked into the effective attention
   temperature. In practice the perturbation is far too small to matter, but
   it's a meaningfully different situation from a pure parsing bug like the
   sympy AutoLev case, where fixing the constant changes nothing else. This
   is a real, confirmed, repeated hand-typed-constant bug - just not a
   consequential one.

2. **onnx** - `onnx/reference/ops/aionnxml/_common_classifier.py:71`:

   ```python
   def compute_probit(val: float) -> float:
       return 1.41421356 * erf_inv(val * 2 - 1)
   ```

   The exact value is **sqrt(2) = 1.4142135623730951**; the literal is
   truncated to 9 digits, about 7 digits short. This is the reference
   (non-accelerated) Python implementation of the ONNX-ML probit-based
   classifier op - notable because this file exists specifically to be the
   ground truth other ONNX runtime backends are checked against. `erf_inv`
   itself is already an approximate rational-function algorithm, so the
   sqrt(2) truncation is folded into a computation that isn't
   bit-exact to begin with; impact is similarly negligible in practice.
   Confirmed still present on `onnx/onnx` `main` as of 2026-07-07.

## Recognized-but-not-a-bug taxonomy specific to this corpus

1. **Frozen backward-compatibility snapshots (jax).** All 8 jax truncations
   live under `jax/_src/internal_test_util/export_back_compat_test_data/` -
   recorded expected outputs from specific historical XLA compiler versions,
   deliberately pinned so a regression test can detect when serialized
   custom-call output changes. These are historical records, not authored
   constants; flagging them as bugs would be the same category error as
   flagging astropy's `codata2010.py`.
2. **Coincidental rationals in synthetic test data (xgboost).** All 11
   xgboost findings are in `xgboost/testing/data.py`, a file that generates
   deterministic pseudo-random-looking test datasets. Values like
   `1425.4767441860465` happening to equal `122591/86` are artifacts of how
   the fixture was constructed (sums/means of small integer ranges), not
   deliberate physical or mathematical constants. Several sit right at the
   confidence gate (surplus 2.0-4.0), which is exactly the calibrated
   behavior described in `docs/confidence-calibration.md` - marginal,
   coincidental matches are expected to occasionally clear the bar at low
   surplus.
3. **A clean null result worth reporting (torch).** PyTorch's 27 recognized
   constants - including 50-digit `M_PI_180`/`M_180_PI` definitions in
   `torch/_refs/__init__.py` and the standard GELU/erf constants in
   `torch/_inductor/codegen/cpp_utils.py` - are all full double precision,
   zero truncations. Worth stating explicitly: this study is not "AI/ML
   libraries are sloppy about constants." PyTorch's own C-derived math
   constants are exactly as precise as they should be; the two real findings
   are narrow and specific, not representative of the ecosystem as a whole.

## Reproduction

```
python -m venv venv
venv/bin/pip install exact-linter
venv/bin/pip install torch --index-url https://download.pytorch.org/whl/cpu
venv/bin/pip install transformers xgboost lightgbm jax jaxlib onnx
KERAS_BACKEND=torch venv/bin/pip install keras
KERAS_BACKEND=torch venv/bin/python scripts/corpus_study.py \
    torch transformers xgboost lightgbm jax jaxlib keras onnx
```

Findings drift as these packages release new versions; the numbers above are
for the versions listed at the top, current as of the study date.
