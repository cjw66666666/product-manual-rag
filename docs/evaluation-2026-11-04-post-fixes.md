# Post-Fix Evaluation 2026-11-04

## Scope

This record covers the current evaluator, `i4` index, development split
`v1-curated`, and the generator/verifier configured in the local `.env`.
The locked split was not modified.

Before the fixes, the same verifier version completed three development runs
at 73.3%, 76.7%, and 76.7% pass rate, for a mean of 75.6%.

## Root Causes

1. `huawei_c5e_gen4` was bound to both the C5e Gen4 manual and the legacy C5e
   manual. Retrieval could therefore return correct text from the wrong
   product generation.
2. The C7 product was also bound to an unrelated Aolynk CB304n manual.
3. Reranking could push expected evidence from RRF rank 4 or 5 below the final
   six-item context.
4. Two development cases targeted evidence that did not match the question:
   a charging question targeted a low-battery warning, and a system-settings
   question targeted keyboard settings.

## Fixes

- Removed the ambiguous bare `C5e` alias from the C5e Gen4 product.
- Made seeding remove obsolete aliases for seeded products.
- Added migration `20261104_0007` to deactivate the contaminated C5e Gen4 and
  C7 document bindings.
- Changed final context selection to fuse the coarse RRF ranking and the
  reranked ordering with a second reciprocal-rank-fusion pass.
- Corrected only the affected development cases. The locked split remains
  unchanged.

## Current Development Result

| Metric | Value |
| --- | ---: |
| Passed | 29 / 30 |
| Pass rate | 96.7% |
| Mode match | 96.7% |
| Required facts hit | 96.2% |
| Citation hit | 96.2% |
| Recall@20 | 100% |
| Recall@30 | 100% |
| Final Top 6 hit | 100% |
| Average latency | 11.72 s |
| P95 latency | 47.38 s |
| Invalid citations | 0 |
| Errors | 0 |

The remaining development failure is `huawei_hm740-003`. The expected evidence
was present in the final context but the generator refused to answer. This is
currently classified as generation instability rather than a retrieval or
data-scope failure.

## Locked-Split Re-Evaluation

The original locked split was not modified. Because it has already been used
for earlier comparisons, this is a regression re-evaluation rather than a
clean blind test.

| Metric | Value |
| --- | ---: |
| Passed | 26 / 30 |
| Pass rate | 86.7% |
| Mode match | 93.3% |
| Required facts hit | 88.5% |
| Citation hit | 88.5% |
| Recall@20 | 100% |
| Recall@30 | 100% |
| Final Top 6 hit | 100% |
| Average latency | 9.50 s |
| P95 latency | 29.10 s |
| Invalid citations | 0 |
| Errors | 0 |

The four locked-split failures are `huawei_c5e_gen4-009`,
`huawei_b5_341w-006`, `huawei_b5_341w-008`, and `huawei_m272q-010`.
Two are refusals despite expected evidence; the others are answer-fact
coverage and citation-matching gaps.

## Verification

- Full `pytest` suite passes.
- `ruff check .` passes.
- `mypy src tests` passes.
- Alembic is at revision `20261104_0007`.

The output reports are `reports/eval-rrf-fusion-dev-v1-20261104.json` and
`reports/eval-rrf-fusion-test-v1-20261104.json`. Runtime reports are
intentionally Git-ignored.
