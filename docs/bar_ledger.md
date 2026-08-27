# The bar ledger — one row per pre-registered bar, one denominator

Built 2026-08-12 after the manuscript review found the scorecard counted bars and failures in two
different units. **This file is the single source of truth for any "N of M bars" statement** in the
manuscript, the abstract, or any correspondence. Verdicts are carried from the findings docs and
the frozen JSONs, one bar per row, no grouping.

| # | exp | bar | verdict |
|---|---|---|---|
| 1 | E1 | H1 — ≥90% of Verified-Technical pass at ≥0.80; median ≥0.95 | **FAIL** (89.3 / 89.7 on two configs) |
| 2 | E1 | H2 — marginal AUROC ∈ [0.45,0.65] all nine, stratification moves <0.05 | PASS on range; **certification clause FAILED** → stratified-only fallback |
| 3 | E1 | H3 — modal + quantity are the two highest classes, ≥0.97, ≥7/9 | **FAIL** 0/9 (both partitions) |
| 4 | E1 | H4 — every fitted repair drops ≥0.10 on bis | **FAIL** — improved instead (the sign-flip law) |
| 5 | E1 | H5 — mean AUROC decays g1→g2→g3, total ≥0.10 | **FAIL** (floor effect; magnitude short) |
| 6 | E2 | H1 — α ∈ [0.8,1.2] for the mean-pooled set | **UNRESOLVED** (7/10 spline-only; membership pending) |
| 7 | E2 | H2a — AUROC <0.60 by L=512, SPLICE raw | PASS **excluding 7 vacuous configs** |
| 8 | E2 | H2b — <0.65 by L=1024, caliper | PASS **excluding vacuous** |
| 9 | E2 | H2c — production ≤0.55 at every bin | PASS |
| 10 | E2 | H3a — AUROC(early)−AUROC(late) ≥0.05 for ≥half | **FAIL** 0/10 (sign inverted) |
| 11 | E2 | H4 — miss ≥0.95 @0.85 for L≥256; ≥0.90 @0.95 for L≥128 | PASS excluding non-evaluable |
| 12 | E2 | H5 — \|r\| < 0.10 by L=512 | PASS |
| 13 | E2 | H6 — held-out cells inside the fitted bands | **FAIL** 69/101 |
| 14 | E3 | HE3-1 — caliper collapses elicited separability | **FAIL** 0/9 → minimal-pairhood criterion |
| 15 | E3 | HE3-2 — every config ≥0.80 naive on QQP | PASS 9/9 |
| 16 | E3 | HE3-3 — all nine inside [0.50,0.75] on PAWS | **FAIL** (production 0.679 highest of nine) |
| 17 | E3 | HE3-4 — no shipped-threshold cell >0.70 balanced accuracy | **FAIL** (28 cells) |
| 18 | E3 | HE3-5 — naive AUROC ranks by coupling magnitude | **FAIL** 1/9 |
| 19 | E4 | B1 — practical floor >0.40 for ≥7/9 on errata | **FAIL** 1/9 |
| 20 | E4 | B2 — practical floor >0.60 for ≥5/9 | **FAIL** 0/9 |
| 21 | E4 | B3 — observed min ≥ hard floor in 100% of cells | **SCOPE FINDING** (2 configs breach the cone condition) |

## The counts, stated once

- **21 pre-registered bars** across four experiments (E1 5, E2 8, E3 5, E4 3). E2's H3b is excluded:
  it was demoted to a reported construction fact before the tag and carries no pass/fail.
> **⚠ CORRECTED 2026-08-13.** The block below previously read *11 failed outright* in its heading
> and *12* in its own parenthetical, listed *5 clean passes (rows 9, 11, 12, 15, and row 2's range
> clause)* — counting row 2 both as the boundary failure and as a clean pass, so the decomposition
> summed to 22 — and filed row 21 as a *scope finding* rather than a verdict. Two 2026-08-12
> rulings had never reached it: **E4-B3's verdict is FAIL** (the scope finding is its
> interpretation; `findings_e4` states "the verdict remains FAIL and is reported as FAIL"), and
> **E2-H4 is a pass qualified by non-evaluability**, not a clean pass. Recomputed from the rows.

- **13 failed outright** (rows 1, 3, 4, 5, 10, 13, 14, 16, 17, 18, 19, 20, 21). B1 and B2 are
  separate bars with separate thresholds and are counted separately. Row 21 is E4-B3.
- **1 boundary failure** (row 2's certification clause, which triggered its registered fallback).
  Its range clause passed, but the row is one bar and is counted once, here.
- **1 unresolved** (row 6).
- **3 passes qualified by exclusion** (rows 7 and 8 by vacuity, row 11 by non-evaluability).
- **3 clean passes** (rows 9, 12, 15).

13 + 1 + 1 + 3 + 3 = **21**. Every row is counted exactly once.

**The canonical sentence: "Of 21 pre-registered bars, 13 failed outright, one failed at its
certification clause, one is unresolved, and three passed only for the configurations able
to evaluate them."** (Form re-ruled 2026-08-26 to numerals for numbers over 10; counts
unchanged; see the JSON `form_note`.) Any shorter form must be a strict weakening of this,
never a different arithmetic. The counts are derived from the rows by `scripts/recompute_headline_numbers.py`, which
now tallies the rows rather than reading a stored summary.

The manuscript's previous "six of sixteen" was wrong twice: sixteen excluded E4's three bars while
§8 tabulated them, and six counted table *rows* (some grouping four bars each) rather than bars.
Corrected everywhere 2026-08-12.
