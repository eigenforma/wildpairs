# Errata label-noise audit — closed, trigger fired, and the label axis becomes a finding

**Status: CLOSED 2026-08-11.** Two blind seats (A: firewalled Claude context; B: gpt-oss-120b on
Forge, temp 0) judged the 300-pair stratified Verified-prose packet under the construct rubric
(`docs/annotation_protocol_errata.md`); κ(A,B) = **0.6813**, raw agreement 88.7%; the operator
adjudicated all 34 disagreements (sitting page, labels sealed throughout: 23 different / 8 same /
3 unjudgeable). Recompute: `scripts/close_errata_audit.py`, `scripts/promoted_primary_auroc.py`;
frozen: `results/verification/errata_audit_final.json`, `promoted_primary_auroc.json`.

## The construct-vs-institution matrix (the numbers the paper was missing)

- **Technical precision 95.2%** (139/146 judgeable adjudicated meaning-changing; Wilson 90.4–97.7)
  — and the two headline classes are **spotless: kw2119 47/47, number 49/49**. "Other" 86%.
- **Editorial leak 66.0%** (99/150 adjudicated meaning-changing; Wilson 58.1–73.1). Two-thirds of
  the institution's Editorial corrections change what the span asserts. This is not seat noise
  (κ 0.68; the operator confirmed 23/34 contested items) — it is **proxy divergence**: IETF's
  Editorial answers "does it affect the technical content of the RFC," our construct asks "does
  this span assert something different." A corrected cross-reference, identifier, or field name
  is Editorial to the institution and a content change under the construct.
- Noise rates ρ_T = 0.048, ρ_E = 0.660 → attenuation 0.292 → **max observable AUROC on
  institution labels = 0.646** for a perfect span-level meaning-change detector. The executed
  H2 numbers must always carry this ceiling: stratified 0.50–0.52 against a 0.646 ceiling.
- **A5 promotion trigger: FIRED** (0.66 ≫ 0.15). Per the registered rule, the adjudicated
  300-subsample is promoted to the primary decision corpus.

## Promoted-primary decision AUROC (construct labels, frozen sweep cosines — post-hoc by construction, primary by trigger)

n = 296 judgeable (238 changing / 58 preserving; the stratified sample, not the population —
population-reweighted figures are a named follow-up; weights known from the class pools).

| scorer | g1 AUROC | g2 | note |
|---|---|---|---|
| **token-Jaccard alone** | **0.772** [0.712, 0.837] | — | the word-counting baseline |
| mxbai-embed-large-v1 | 0.804 | 0.774 | best encoder |
| e5-base-v2 [query:] | 0.803 | 0.770 | |
| bge-base-en-v1.5 | 0.797 | 0.755 | |
| gte-base | 0.778 | 0.748 | |
| e5-base-v2 [no prefix] | 0.773 | 0.732 | |
| all-MiniLM-L6-v2 | 0.770 | 0.741 | |
| nomic [clustering:] | 0.752 | 0.722 | |
| all-mpnet-base-v2 | 0.729 | 0.694 | |
| production nomic-MRL-256 | 0.714 | 0.680 | **below the word-counting baseline** |

Cluster CIs (by RFC doc) overlap the Jaccard baseline for **all nine** configurations: under
construct labels, no encoder demonstrably exceeds counting words, and the production path sits
below it.

## What this does to the claims

1. **The thesis holds on both axes, and the axis pair is the demonstration.** Institution axis:
   overlap near-matched (δ −0.10), cosine ≈ chance (0.50–0.52 stratified) against a 0.646
   noise ceiling. Construct axis: overlap strongly aligned (Jaccard AUROC 0.772), cosine ≈
   0.71–0.80 — i.e., exactly the word-counting grade the coupling supplies, and no more. The
   score tracks wording wherever the wording goes; the *labels* decide whether that looks like
   success or blindness.
2. **The sign-flip law gains a fourth regime — and a sharper statement.** Authored (inverted) /
   errata-institution (near-zero) / bis (aligned) / **errata-construct (aligned)**: the last two
   rows show the coupling orientation is a property of the **labeling process**, not only the
   authoring process. One corpus, two label axes, two orientations.
3. **The deployment claims strengthen.** H1's pass rates now carry construct confirmation: the
   corrections the gates approve are 95% construct-verified meaning changes (100% in the modal
   and quantity classes — Paper A §6's worst classes, again). The audit-altitude sentence gains
   its qualifier: "no encoder distinguishes the *institution's* classes better than 0.52
   stratified (ceiling 0.646); under adjudicated span-level labels every encoder reaches only
   word-counting-grade separability (≤ the Jaccard baseline), and the production path falls below
   it."
4. **The leak is the practitioner headline of the arm:** the institution's own triage files
   two-thirds of span-level meaning changes as Editorial — the same surface-first blindness the
   gate class exhibits, now measured in the labeling pipeline the ecosystem would naturally reach
   for as ground truth.

## Caveats, stated plainly

Stratified sample (T-side balanced over classes; E-side uniform), so promoted-primary AUROCs are
sample-frame estimates; population reweighting is queued. Heavy class imbalance (238/58) widens
the preserving-side CIs. The construct rubric counts reference/identifier corrections as content
changes by rule 4 — defensible (a reader acts differently), but the paper must print the rubric
beside the number. All promoted-primary numbers are post-hoc relabelings of frozen scores; the
prereg bars were judged on institution labels and their verdicts stand unchanged.
