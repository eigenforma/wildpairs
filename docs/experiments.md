# Paper B — Two Vetted Experiments (2026-08-05)

Product of a 14-agent design/judge/verify workflow: 6 designer lenses → 12 candidates → 3-judge panel → complementary-pair selection → adversarial novelty + feasibility verification (all four checks returned NOT REFUTED, high confidence). Full run record: session workflow `wf_61ec9d1f-b34`.

## The frame

Paper A showed, with an 80-pair authored instrument, that cosine-threshold gates measure wording where they are deployed to measure meaning. Paper B measures that failure **where it actually lives** — in text nobody authored for the audit, and at the passage lengths deployed gates actually compare.

- **E1** takes meaning-change labels an institution already produced (25 years of IETF errata verification) and asks whether any encoder configuration at any shipped operating point can see what the verifiers saw.
- **E2** supplies the quantitative law the external reviewer asked for: how the flip-vs-faithful decision signal decays as passage length grows, and the critical length L* at which every configuration falls below every shipped threshold.

The two interlock: the RFC corpus is E1's label source and E2's held-out host register (one shared frozen snapshot); E1 observes dilution in the wild across three granularities, E2 titrates it causally. Observation plus mechanism — the same one-two structure as Paper A's deployed audit plus factorial instrument.

Upgrade path for the verdict: from "an 80-pair authored instrument says the gate fires backwards" to "the institution's own labels say the gate cannot see verified meaning changes at scale, and here is the measured law by which the blindness deepens with context length."

---

## E1 — The Institution Flagged It: cosine gates vs. 3,583 IETF-verified Technical/Editorial corrections

**Research question.** When the IETF's own verifiers have already labeled a minimal edit as Technical (meaning-changing) or Editorial (meaning-preserving), can any of the nine pinned encoder configurations, at any shipped cosine operating point, separate the two classes better than chance — and does the separation survive transfer from errata corrections to bis-revision requirement-strength changes?

**Why this is the ecological result Paper A could not have.** The class label is assigned by a third-party institution with no knowledge of the audit; no text is authored by anyone in the study. The §8 capture channel is severed at the source. And nature nearly runs Paper A's matched design on its own: verified spot-checks (independently reproduced by the feasibility verifier via direct download and re-parse on 2026-08-05) show token-Jaccard medians 0.889 (Technical) vs 0.912 (Editorial) — corrections are minimal edits in *both* classes, so the corpus is naturally overlap-matched.

**Data (all verified by direct download, no credentials anywhere).**
- `https://www.rfc-editor.org/errata.json` — 11.6 MB, 7,991 entries; Verified with both texts non-empty: 1,895 Technical + 1,683 Editorial; 2,412 Held-for-Document-Update as a sensitivity stratum. License: IETF Trust TLP / BCP 78, freely redistributable.
- RFC full text via `rsync.rfc-editor.org::rfcs-text-only` (the `retrieve/bulk` tar.gz URL is stale — use rsync or scripted per-file fetch, shipped as a fetch-and-freeze loader) + `rfc-index.xml` obsoletes relations for the bis held-out corpus.
- Confirmed edit-class counts: ~122 RFC-2119 keyword-strength changes, ~782–809 quantity/number changes — Paper A §6's two worst mutation classes (modal downgrade, quantity drift), now at institutional scale.

**Protocol (amended per verification).**
1. Freeze errata.json. Filter to Verified (primary), Held (sensitivity); exclude ABNF/code/table-only pairs (~636 of 1,895 Technical are majority-code → prose-primary Technical corpus ≈ 1,250, still ample), keep code pairs as a register stratum if n≥200.
2. Diff-localize each pair; emit three granularities: changed-sentence, quoted-passage, section-context (section-context is best-effort — expect 10–30% quote-relocation loss in line-wrapped RFC files; disclose match rate).
3. Machine-classify Technical pairs into edit classes; two annotators verify class AND the Technical/Editorial label on a 300-pair stratified subsample (κ, adjudication, label-noise rate reported — McQuistin et al.'s erratum-5595 case documents the boundary fuzz this measures). Budget ~30 annotator-hours, not 12–16.
4. **Before any encoder loads**, pre-register the overlap-coupling measurement (Jaccard distributions per class, Cliff's δ, permutation test) and freeze the pair list. If overlap-decile stratification moves decision AUROC < 0.05, the corpus is certified as a naturally matched instrument — the thing Paper A had to construct synthetically.
5. Run all 9 pinned configurations offline; score every pair at every granularity; evaluate at cosine 0.30/0.40/0.60/0.80/0.85/0.95.
6. Fit Paper A's repair candidates (per-encoder threshold; logistic on cosine+Jaccard; NLI cross-encoder) on errata.
7. Mine the bis corpus from ALL obsoletes families (not just the marquee three — the SMTP probe yielded only ~9 raw keyword transitions with 30–50% artifact rates, so: align through intermediate revisions, pre-register an artifact taxonomy (case normalization, prose→keyword normalization, subject rewording), and a minimum-positives gate of n≥100 human-verified genuine strength transitions; 200-pair two-annotator alignment audit).
8. Frozen evaluation of every fitted object on bis. Cluster bootstrap by RFC document. All results frozen JSON, one-command reproduction.

**Pre-registered hypotheses.**
- H1: at shipped thresholds ≥0.80, ≥90% of Verified-Technical corrections pass the gate at quoted-passage granularity; median Technical cosine ≥ 0.95.
- H2 (the new claim beyond Paper A): marginal Technical-vs-Editorial AUROC in 0.45–0.65 for all nine configurations, and overlap-stratification moves it < 0.05 — *even when the confounder is naturally absent, cosine carries almost no decision content*.
- H3: modal-keyword and quantity classes score the highest cosines among Technical classes (median ≥ 0.97) — §6's worst-classes finding at 10–40× scale.
- H4: errata-fit calibrations drop ≥ 0.10 when frozen-evaluated on bis — §7's instability replicated across two *natural* generative processes (correction vs. deliberate revision).
- H5: detection AUROC decays ≥ 0.10 from changed-sentence to section-context granularity.

**Novelty (adversarially verified, 10 targeted searches).** The only prior academic use of RFC errata is McQuistin et al. (TMA 2023) — a process-characterization study, zero text models. No errata or bis-diff dataset exists on HF. Nearest revision corpora (IteraTeR, VitaminC, DIFFQG, WikiAtomicEdits, WNC) all use researcher/crowd labels, none audits gates. Required citations to pre-empt reviewers: McQuistin et al. as dataset provenance; the 2025–26 semantic-cache calibration cluster (vCache; arXiv:2606.19719) as independent corroboration whose calibration-style fixes E1 tests across a natural source transfer; a cheap ~500-pair VitaminC side-by-side cell to answer "why not just use VitaminC?". Release the mined bis requirement-change pairs as a standalone citable dataset artifact.

**Lab sizing.** Embedding pass is trivial (~4,000 pairs × 3 granularities × 9 configs — under an hour on Forge). The swarm's real work: LLM-assisted edit-class pre-labeling with small-model bulk pass → 120B arbitration on disagreements (Forge+Agora), and the bis mining sweep over *hundreds* of obsoletes families, which at week-long scale can produce the full requirement-change dataset rather than the minimum n≥100. Wall-clock 2–3 weeks including annotation and pre-registration freeze.

---

## E2 — The Dilution Law: length-titrated decay of the polarity-decision signal, CondaQA payloads in real host passages

**Research question.** As passage length L grows, does the embedding-cosine decision signal separating a meaning-flip pair from a faithful-paraphrase pair decay according to a measurable law, and at what critical length L* does every encoder configuration — including the bge/mxbai class at AUROC 0.79–0.90 sentence-scale in Paper A — fall below usable discrimination and below every shipped operating point?

**Headline reframe (per verification):** the ~1/L cosine-gap decay for mean-pooled encoders is near-arithmetic — pre-register it as *calibration*, not discovery. The headline is the **per-encoder critical length L\*** at which flip-vs-faithful AUROC falls below usable discrimination and below every shipped threshold — which no prior work measures.

**Data (all verified accessible, licensed).**
- CondaQA (HF `lasha-nlp/CONDAQA`, Apache-2.0 confirmed; EMNLP 2022, 150+ citations): **1,289 unique passages** (474/115/700 splits — the "~1.7k" figure was wrong), each with crowd-authored paraphrase / scope / affirmative(=reversal) edits. Payload minimal pairs authored by many workers, for QA, not for this audit.
- enwiki-20210701 (CondaQA's exact source snapshot, preserved on archive.org) — native-context arm + splice-host fit domain. CC BY-SA.
- PMC Open Access CC-BY subset — held-out host domain 1. Use the **PMC Cloud Service / AWS Open Data mirror** (the FTP path retires this month, August 2026).
- RFC corpus — held-out host domain 2 (shared frozen snapshot with E1). Do not redistribute spliced RFC text: ship tarball checksum + deterministic splice-regeneration script (Paper A's own "read but not redistributed" precedent).

**Protocol (amended per verification).**
1. Mine anchor sets (s, reversal, paraphrase, scope). CondaQA workers sometimes edited *beyond* the negated sentence — pre-register a yield pipeline keeping anchors where both edits are recoverable as single-sentence substitutions; fallback target ≥400 anchors (NevIR extracted 2,556 pairs from the same source — headroom exists); report the measured single-sentence-edit rate as a dataset finding; reconstruct multi-sentence items by substituting the edited sentence into the unmodified passage, flagged and analyzed separately.
2. Two-annotator relabel of a 200-anchor subsample for standalone semantics (κ, adjudicated drops). Budget ~2 days.
3. Titrate L ∈ {64, 128, 256, 512, 1024, 2048, 4096} (the 32-token bin is infeasible — CondaQA payloads average ~38+ tokens; drop any anchor whose payload exceeds half its bin). Two arms: NATIVE (real surrounding article text, natural edit position; demoted to supporting-ecological — substring-match rate against the dump will be ~70–90%) and SPLICE (primary controlled instrument: byte-identical host text around the payload at early/middle/late positions). Both pair members share byte-identical host context — only the payload differs.
4. Embed with the 9 pinned configurations + long-context nomic at full 8192 window. For 512-window encoders, L>512 is the **truncation regime**, analyzed separately: a late-position flip outside the window is a miss *by construction* — a real deployment failure, reported as such.
5. Per (encoder, L, position, domain): decision AUROC, cosine-gap distribution, miss rate at the six shipped operating points.
6. Measure the imported CondaQA overlap-coupling per edit type (affirmative edits are high-overlap, paraphrases lower — Paper A's confounder arrives with the dataset): analyze raw AND caliper-matched (payload-Jaccard within ±0.05); use the scope-edit class as the built-in high-overlap flip control; elevate **the confounder's own dilution with L** to a named secondary result (pre-registered: |r(passage-Jaccard, class)| < 0.10 by L=512 — which mechanically explains why §7's overlap-conditioned repair is information-starved at deployment lengths).
7. Fit Δ(L) = Δ₀·(k/L)^α per encoder on Wikipedia hosts (report a monotone-spline nonparametric decay alongside); pre-register α and L*(AUROC=0.75), L*(AUROC=0.55); evaluate the frozen curves on PMC and RFC hosts (held-out source change). Frozen JSON, one-command offline reproduction.

**Pre-registered hypotheses.** H1: α ∈ [0.8, 1.2] for mean-pooled encoders (calibration). H2: every configuration below AUROC 0.60 by L=512 ecological / 0.65 by L=1024 matched; production nomic-MRL-256 at chance at every L. H3: late-position flips missed more (Δ≥0.05 at L=512 for half the configurations; miss rate 1.0 by truncation for 512-window encoders at L>512). H4: at the 0.85 drift cut, flip miss rate ≥0.95 for all configurations at L≥256; at 0.95, the contradicting passage is judged redundant ≥90% at L≥128. H5: confounder dilution (above). H6: Wikipedia-fit curves predict PMC/RFC AUROC within 95% CIs. Add the NevIR anchor as a confirmatory prediction: configurations NevIR scores near-random at passage scale should show Δ₀ already small at L=64 — an externally anchored intercept.

**Novelty (adversarially verified — three near-neighbors found that the designer missed, all must be cited).**
- **NevIR** (EACL 2024) + SIGIR 2025 reproduction: builds contrastive pairs *from CondaQA*, shows bi-encoders rank at/below random on negation. No length axis, no position axis, ranking not pairwise gate decisions, no thresholds, no decay law. Report NevIR's pairwise-accuracy metric on the shortest-L cell as a bridge baseline.
- **Semantic Needles in Document Haystacks** (arXiv:2604.18835): same design geometry but LLM-judge scoring only, 1–19 sentences, procedural needles, no AUROC/thresholds/decay/transfer. E2 is the embedding-gate, decision-theoretic counterpart at ~100× the length range. Optionally add one LLM-judge arm at matched conditions — that comparison is itself new.
- **Lost in a Single Vector / Evidence Dilution Index** (arXiv:2606.18781): dilution is a named retrieval-side quantity in 2026; adopt EDI as a secondary metric or state why the pairwise cosine-gap is what a gate actually thresholds. Frame E2 as measuring *what dilution destroys* (a safety decision), not *that dilution occurs*.
- Also cite: arXiv:2412.15241 (positional bias — their irrelevant-text insertions are the null probe, the flip payload is the treatment) and arXiv:2603.21437 (pooling/semantic-shift theory — E2 is the empirical calibration it predicts).

**Lab sizing.** ~1–2M short embedding calls: 1–3 days on Forge alone; comfortably a two-box overnight when sharded Forge/Agora over the 40GbE link. The week-long budget buys the full grid *plus* extension arms: the in-house **MRL family across truncation dims** (does L* shrink with dim? Paper A found MRL-256 at chance at sentence scale) and the in-house **native-Poincaré encoders** (Paper A §9 proved post-hoc projection is a no-op; whether *natively trained* hyperbolic encoders hold polarity at length is exactly the case §9 explicitly left open — no one has measured L* in hyperbolic space).

---

## Deferred to Paper C (clean, self-contained — not holes in Paper B)

- **Artifact Share** (panel score 130.5, second only to E1): what fraction of each trusted negation/paraphrase benchmark's reported separability — and of negation-aware encoders' reported gains (Truong et al. 2025 etc.) — survives lexical-overlap matching.
- Negation-aware encoder evaluation on the E1 errata benchmark.
- The small-model scaffolding program (separate track; see memory note): scaffolding structure as manipulated variable, attempt-count-to-success as outcome, small-vs-large model as comparison — the swarm's tiered small→120B escalation pipelines are themselves prototype scaffolding.

## Runner-up record (panel totals /150)

#6 IETF errata 131 · #3 Artifact Share 130.5 · #0 Natural revision histories 126.5 · #4 Dilution Law 122.5 · #1 Dilution curve (ecological) 121 · #2 Composed factorial 120.5 · #7 FDA drug labels 120.5 · #5 Regulatory gates-at-length 119. The pair-selector chose #6+#4 over #6+#3 because 6 and 3 are methodological twins (same analytic move, two corpora) while 6+4 covers ecological scale *and* a new quantitative dimension, answering reviewer critiques (a), (b), (c) simultaneously.

---

## Corrections and updates (2026-08-08, five-lens adversarial review)

The record above is preserved as written on 2026-08-05; **operative specifications live in the preregistrations** (review record: `docs/reviews/adversarial_review_2026-08-08.md`). Corrections that must not propagate into the paper:

- E1's title count "3,583" → **3,578** (1,895 + 1,683). One dated snapshot number everywhere.
- "six shipped operating points" → Paper A's canonical phrasing is **five** shipped operating points (0.30/0.40/0.80/0.85/0.95) **plus the audited guard's cosine-0.60 equivalent, evaluated separately** (Paper A §5/§6). Same reviewers will diff the count.
- "~100× the length range" (vs Semantic Needles) → **~10×** (their ceiling ≈ 19 sentences ≈ 400–500 tokens; E2's is 4,096). "Procedural needles" → "procedurally *generated* perturbations" (their corpus is plain Wikipedia).
- vCache is arXiv:**2502.03771** (ICLR 2026); arXiv:2606.19719 is a *different* paper (Baral et al., "Closing the Calibration Gap in Semantic Caching"). Cite both, separately.
- CondaQA "150+ citations" is unsupported by a verifiable source (Semantic Scholar: 50) — drop the number or attribute the claim.
- "the case §9 explicitly left open" → "the case §9's no-op proof does not touch" (§9 scopes native training out; it never poses the question).
- Held stratum: 2,412 is *all* Held; **2,214** carry both texts (845 T / 1,369 E) — and Held's class-overlap coupling is ≈3× the Verified gap, so the sensitivity stratum is *more* confounded than the primary.
- CondaQA payload length: median **23**, mean 24.8, p90 38 whitespace tokens — "average ~38+" was the p90.
- The quantity-class "~782–809" range: the pinned definition (`\d+(\.\d+)?` multiset, prereg-e1 §2) reproduces **782 exactly**; unpinned variants ranged 545–930, so only the pinned number may appear.
- PMC: "FTP retires August 2026" understated — the legacy S3 prefix `deprecated/oa_comm/txt/all/` is deleted **on/after 2026-08-24**; the E2 slice must freeze before then (PLAN §5 ask 1).
- Must-cite additions from the scoop hunt (neither headline scooped): **MeTMaP** (arXiv:2402.14480, FORGE 2024 — metamorphic audit of 203 vector-matching configurations; nearest prior gate-audit work; flagged into Paper A too), **Length-Induced Embedding Collapse** (arXiv:2410.24200 — the ancestor the cited pooling-theory line argues against), the **3GPP change-request NLP line** (Chen et al., USENIX Security 2022; TSpec-LLM) as prior institutional-label+embeddings work differentiated in one clause, **PSMBench/RFC2PSM** (NeurIPS 2025 D&B) as the hedge on RFC-corpus novelty (errata remain untouched — verified against HF and 47 NevIR citations), and WNC differentiated on label *semantics*, not provenance.
