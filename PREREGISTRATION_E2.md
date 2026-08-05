# PREREGISTRATION — E2: The Dilution Law

> **STATUS: DRAFT.** Binds nothing until frozen by tagged commit `prereg-e2`. The tag lands
> only after the host slices of §2 are pinned (PMC slice definition, native-arm match rate);
> **no encoder output will be observed on any titrated passage before the tag.** Everything in
> §6 is encoder-blind lexical computation.

## 1. Population and payloads

- Anchors: `corpus/e2_dilution/anchors_frozen.jsonl` — **959 anchor sets** (of 1,273 candidates carrying original + paraphrase + affirmative edits) where BOTH the paraphrase (edit 1) and affirmative/reversal (edit 3) are single-sentence *substitutions* against the original passage, per the pinned diff algorithm (`harness/e2/build_anchors.py`; identical to the estimator in `scripts/verify_condaqa.py` by construction). 903 also carry the scope edit as the high-overlap flip control. Splits 363/86/510 (train/dev/test); split membership is recorded but pooled for the titration (CondaQA's QA splits are irrelevant to pairwise gate decisions; no model is trained).
- Pair classes per anchor: **flip** = (payload_orig → payload_affirm), **faithful** = (payload_orig → payload_para), **scope** (secondary) = (payload_orig → payload_scope).
- Every anchor's paraphrase and affirmative edits modify the SAME sentence slot (measured rate 1.0), so both members of every pair share byte-identical host context with the payload at an identical position.

## 2. Design

- **SPLICE arm (primary).** The payload sentence is embedded in real host text at controlled position ∈ {early, middle, late} (first/middle/last decile of sentence slots), titrated at L ∈ {64, 128, 256, 512, 1024, 2048, 4096} tokens (tokenizer: the encoder's own; bin construction by whitespace-token count ×1.3 safety factor, recorded). Anchors whose payload exceeds L/2 drop from that bin only. Hosts: **enwiki-20210701** (fit domain; frozen, sha256 `cf5ab6b3…`), **PMC-OA CC-BY slice** (held-out 1; slice pinned at tag time from the AWS mirror by ascending PMC ID, body ≥ 6,000 tokens, first 2,000 articles), **RFC text corpus** (held-out 2; frozen shared snapshot with E1; spliced RFC derivatives are never redistributed — regeneration script + checksums only).
- **NATIVE arm (supporting, ecological).** The CondaQA passage extended with its actual surrounding article text from the pinned dump; expected substring-match rate 70–90%, disclosed; failures drop from NATIVE only.
- **Encoders.** The nine pinned polaritycheck configurations + long-context nomic at full 8192 window. For 512-window encoders, L > 512 is the **truncation regime**, analyzed separately: a late-position flip beyond the window is a miss by construction and is reported as deployment behavior.
- **Measurements** per (encoder, L, position, host): flip-vs-faithful decision AUROC over anchors; cosine-gap Δ distributions; miss rate at operating points {0.30, 0.40, 0.60, 0.80, 0.85, 0.95}.
- **Fits.** Δ(L) = Δ₀·(k/L)^α per encoder on Wikipedia hosts, plus a monotone-spline nonparametric curve (the law does not depend on the parametric form). Critical lengths L*(AUROC=0.75) and L*(AUROC=0.55) per encoder. Frozen fitted curves are evaluated predictively on PMC and RFC hosts.

## 3. Hypotheses and bars

- **H1 (calibration, not discovery):** α ∈ [0.8, 1.2] for mean-pooled encoders — the near-arithmetic dilution of a one-sentence perturbation; deviations by CLS-pooling/attention encoders are reported as findings.
- **H2 (the headline — universal failure length):** every configuration, including the bge/mxbai class (AUROC 0.79–0.90 at sentence scale in Paper A), falls below flip-vs-faithful AUROC 0.60 by L=512 (ecological) and 0.65 by L=1024 (caliper-matched); the production nomic-MRL-256 path is ≤ 0.55 at every L.
- **H3 (position):** AUROC(early) − AUROC(late) ≥ 0.05 at L=512 for ≥ half the configurations; truncation-regime late-position miss rate = 1.0 for 512-window encoders at L > 512.
- **H4 (shipped thresholds):** at cosine 0.85, flip miss rate ≥ 0.95 for all configurations at L ≥ 256; at 0.95, the contradicting passage is judged redundant ≥ 90% at L ≥ 128.
- **H5 (confounder dilution):** |r(whole-passage token-Jaccard, class)| < 0.10 by L=512 — the overlap covariate is information-starved at deployment lengths, mechanically explaining Paper A §7's repair failure.
- **H6 (transfer):** Wikipedia-fitted decay parameters predict PMC and RFC AUROC within the fitted curves' 95% CIs.
- **External anchor (NevIR):** configurations NevIR scores at/below random on passage-scale negation ranking show Δ₀ already < 0.05 at L=64 — the intercept is externally anchored; NevIR's pairwise-accuracy metric is reported on the L=64 cell as a bridge baseline.

## 4. Analysis

AUROC with bootstrap CIs over anchors (10,000, seed 20260805); ecological (raw) AND caliper-matched (payload-Jaccard within ±0.05) analyses both reported per Paper A §3 discipline; scope-edit class as high-overlap flip control; per-length-bin r(Jaccard, class); κ from the E2-P5 two-annotator relabel (200 anchors, standalone semantics) reported as a label-noise ceiling; all results frozen JSON, one command, offline.

## 5. Sequencing

Host slices pinned → `prereg-e2` tag → titration build (encoder-blind) → relabel arm in parallel → embedding sweep (Forge/Agora shards, config-hash-verified merge) → fits on Wikipedia → frozen prediction on PMC/RFC. Amendments after the tag file below the tag line.

## 6. Computed before this draft (encoder-blind, lexical, disclosed)

From `harness/e2/build_anchors.py` + `scripts/verify_condaqa.py` on the frozen snapshot (all counts two-source checked where a second source exists): 14,182 rows, 1,289 passages, 474/115/700, zero cross-split PassageID overlap; single-sentence rates paraphrase 0.909 / scope 0.790 / affirmative 0.764; **959 anchors frozen, 903 with scope control, same-slot rate 1.0**; payload token-Jaccard medians **paraphrase 0.7692 vs affirmative 0.7667 (median gap −0.0025** — the imported CondaQA confounder is negligible at the median; means 0.6759 vs 0.7147, gap 0.039, so the caliper-matched secondary analysis stays mandatory**)**; payload length median 23 words, p90 39 (motivates the L≥64 grid floor and the L/2 drop rule).
