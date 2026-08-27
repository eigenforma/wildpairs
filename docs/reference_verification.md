# Reference verification — every characterization checked against its primary source

**Why this file exists.** The Wave 1 emails ask five authors to check how we describe *their*
work. Doing that while carrying a loose description of anyone else's would be indefensible. So
before release, every sentence this paper writes about another paper was sent to a verifier with
the primary source, and ruled ACCURATE / OVERSTATED / UNDERSTATED / WRONG. The corrected sentence
is the one that goes in the manuscript. This file is the audit trail; `docs/references.bib` is the
bibliography it produced.

Verifiers were instructed to err toward strictness over generosity.

---

## Batch 1 — the gate and cosine-validity line (verified 2026-08-12)

### MeTMaP — arXiv:2402.14480, IEEE/ACM FORGE '24 · **WE WERE WRONG**
Our draft called 41.5% MeTMaP's *detection accuracy*. It is not. It is the accuracy of the best
of the 203 vector-matching combinations **on MeTMaP's generated triplets**, i.e. the thing being
measured, not the measurer. Publishing that would have inverted subject and object in a sentence
about the nearest prior work in our own area. Venue is **IEEE/ACM** FORGE, not ACM. The counts
(203 configurations, 29 models × 7 metrics, 8 metamorphic relations, 6 datasets) all verified.

> **Publish:** the nearest prior systematic probe of the vector-matching layer: MeTMaP, a
> metamorphic testing framework that builds sentence triplets from 8 metamorphic relations derived
> from 6 NLP datasets and runs them against 203 vector-matching configurations (29 embedding
> models × 7 distance metrics), finding that accuracy falls by more than 78% on average relative
> to the original datasets, with the best of all 203 combinations reaching only 41.51%.

*Note: describing a tool contribution purely as an "audit" undersells it; "systematic probe" is
the fairer word, and we should keep "nearest prior" only because we are willing to defend it.*

### Steck, Ekanadham & Kallus — arXiv:2403.05440, WWW '24 Companion (4pp) · **OVERSTATED ×2**
1. **Scope.** The analytic result covers *regularized linear models*, where closed-form solutions
   exist. Deep models appear in a discussion section, not a proof. Our "over learned embeddings"
   generalized a result the authors explicitly bounded.
2. **Mechanism.** We wrote "depending on regularization choices," collapsing two distinct
   findings: for some models the similarities are *not unique at all* (underdetermination, which
   does not depend on any choice); for others they are implicitly controlled by the regularization.

> **Publish:** derives analytically, for embeddings from regularized linear models where
> closed-form solutions are available, that cosine similarity can yield arbitrary and therefore
> meaningless "similarities" — non-unique for some models, implicitly controlled by the
> regularization for others — and argues by extension that the combinations of regularization used
> in deep models have implicit and unintended effects on the resulting cosine similarities.

### Length-Induced Embedding Collapse — Zhou et al., **ACL 2025** (not ICLR) · **LEVEL CONFUSION**
Two traps. The venue is ACL 2025 main, Long Papers. And **the arXiv v1 title is the superseded
one** ("…in Transformer-based Models"); the published title reads **PLM-based**. Citing the arXiv
title would look like we read the rejected submission. Our sentence also merged the finding
(longer texts' embeddings *cluster together*, an inter-text distributional inconsistency) with the
mechanism (token features become more similar) — one level down.

> **Publish:** shows that the embeddings of longer texts cluster together — "Length Collapse" —
> producing a distributional inconsistency between short- and long-text embeddings; attributes the
> mechanism to self-attention acting as a low-pass filter whose strength intensifies with length;
> and proposes TempScale, which applies a temperature coefficient to the attention logits before
> the softmax, evaluated on MTEB and LongEmbed.

### vCache — arXiv:2502.03771, **ICLR 2026 (accepted)** · **ACCURATE**
Both halves hold. Minor register note: they write "user-defined," not "user-specified," and our
"cannot serve" is a shade stronger than their three stated consequences (no formal guarantee,
unexpected error rates, suboptimal hit rates). Use their register.

### Baral et al., Closing the Calibration Gap in Semantic Caching — arXiv:2606.19719 · **ACCURATE**
Cleanest in the set. P-CHR AUC and CRR are both their terms and expand as we said. **Preprint
only — do not attribute a conference.**

### Quantifying Positional Biases in Text Embedding Models — arXiv:2412.15241 · **ACCURATE, but we undersell it**
**Venue unconfirmed — do not write NeurIPS.** The Comments field says only "NeurIPS"; no primary
source confirms a workshop. Cite as preprint or ask the authors. And we omit the clause that makes
the finding systematic rather than model-specific:

> **Publish:** documents systematic positional bias in text embedding models **irrespective of
> their positional encoding mechanism**, showing that inserting irrelevant text or removing content
> at the start of a document reduces cosine similarity to the original embedding by up to 12.3%
> more than the same ablation at the end.

### Lost in a Single Vector — arXiv:2606.18781 · **UNDERSTATED + NAMING SLIP**
We credited them with coining "evidence dilution." They did not — that phrase appears only inside
the index name. Their named phenomenon is **document-side early compression**. We also described a
method paper as pure measurement: DICE is a training-free remedy, not just an index.

> **Publish:** identifies document-side early compression as a failure mode of single-vector dense
> retrieval and introduces the Evidence Dilution Index, which measures how far a document-level
> representation falls below the strongest chunk-level evidence in the same gold document; their
> training-free remedy DICE encodes chunks independently and aggregates them into one vector.

---

## Standing lesson

Three of seven characterizations in this batch were wrong or overstated, and every one of them was
wrong in *our* favour — a stronger prior claim makes our contribution look smaller, so the errors
all ran toward diminishing the neighbours. That direction is worth naming, because it is the
direction a reviewer will assume was motivated.

---

## Batch 3 — institutional labels, measurement, statistical precedent (verified 2026-08-12)

- **McQuistin et al. (TMA 2023)** · **"only" is unsupportable.** The paper claims *first*, twice.
  Mirror their claim, not a stronger one — this is the clause the author is likeliest to push back
  on, and he is a Wave 1 recipient. Also: **6,759 is exact, drop the tilde**; the scope is
  understated (they also evaluate three errata-reduction strategies); and "no text model" needs
  qualifying — they do light text handling (subject-to-draft matching, section extraction), just
  no classifier over errata content. Erratum 5595 characterization **verbatim correct**.
- **Jacobs & Wallach (FAccT 2021)** · ACCURATE. Their term is **construct reliability**, and they
  *contribute* fairness-oriented conceptualizations rather than merely importing them.
- **Li et al., Proxy Presumption** · ACCURATE — and now has a venue: **ACL 2026, Oral + SAC
  Highlight**. Cite **v2**. Their phrase is worth using: "measurement by renaming."
- **Chen et al. (USENIX Sec 22)** · method ACCURATE (pipeline is **CREEK**), but the institutional
  Category field is used **only as a pre-filter**, never as feature or label. In a section
  organized around institutional categories, our clause would have read as "they exploit those
  categories." Name the pipeline so the claim is checkable.
- **TSpec-LLM** · **identifier stale** — published at IEEE Globecom Workshops 2024; cite that.
  "Retrieval pipelines" (plural) overstates: one naive-RAG baseline, built as a demonstration.
- **PSMBench** · **two artifacts conflated.** RFC2PSM is the *dataset* and owns all four numbers;
  PsmBench is the *benchmark* over it. 1,580 is exact.
- **Simpson/Yule** · **OVERSTATED, and the pairing is wrong.** Yule 1903 covers association
  *created* by amalgamation, not *reversed*; the reversal reading is Simpson's; the name is
  Blyth's (1972); the phenomenon is anticipated by Pearson et al. (1899). `(Simpson 1951)` alone
  is defensible. `(Yule 1903; Simpson 1951)` is not, unless we write "the Yule–Simpson effect."
- **Chapman et al. 2001 (NegEx)** · **WRONG attribution, and it is in the published Paper A.**
  "Long the standard demonstration that surface similarity does not carry polarity" retrofits an
  embeddings-era argument onto a rule-based clinical paper that makes no claim about similarity at
  all, in a domain (discharge summaries) narrower than we implied. Filed to the Paper A v2 errata
  list. The true adjacent claim: NegEx is the long-standing **baseline for negation detection in
  clinical text**, and any "therefore surface form is insufficient" inference must be marked as
  ours.

## Tally across all three batches

**25 characterizations checked against primary sources; 12 were wrong, overstated, understated, or
mis-scoped — just under half.** Two reached correspondence already drafted to the authors
concerned (McQuistin's "only", Blanco's collapsed finding); one reached the *published* companion
paper (NegEx). Zero identifiers resolved to the wrong work, which is the one thing the earlier
review had already fixed.

The pattern from batch 1 held throughout: errors ran toward diminishing the neighbours or
inflating their support for our framing. That is the direction a reviewer assumes was motivated,
and it is the reason this pass existed.
