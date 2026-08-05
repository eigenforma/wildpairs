# PREREGISTRATION — E1: The Institution Flagged It

> **STATUS: DRAFT.** This document binds nothing until frozen by the tagged commit `prereg-e1`.
> **Declaration at draft time (2026-08-05): no encoder has been loaded against any errata pair. No cosine score over any errata text exists anywhere in this program.** The only computations performed before this freeze are the encoder-blind snapshot verifications listed in §6, all lexical (counts, token-Jaccard, permutation tests), recomputable via `scripts/verify_snapshot.py`.

## 1. Population

- Source: `corpus/e1_errata/errata.json`, frozen snapshot (SHA-256 in `corpus/MANIFEST.json`). Analyses never touch the live URL.
- Primary population: entries with `errata_status_code == "Verified"`, `errata_type_code ∈ {"Technical","Editorial"}`, and both `orig_text` and `correct_text` non-empty after whitespace normalization.
- Sensitivity stratum: `"Held for Document Update"`, same filters, analyzed identically, reported separately, never pooled with primary.
- Exclusion — code-primary pairs: a pair is code-primary if either text has alphabetic-character ratio < 0.70 over non-whitespace characters, or ≥ 50% of its lines match the ABNF/code indicator set (`::=`, `=/`, lines that are purely punctuation/hex/bit-diagram characters). Code-primary pairs form a separate register stratum, reported if n ≥ 200, else only counted. The exact predicate is `harness/lib/filters.py::is_code_primary` at the freeze tag; its yield on the frozen snapshot is reported before any encoder runs.

## 2. Instruments, all fixed before the freeze

- Tokenizer for all lexical statistics: lowercase; tokens are maximal `[a-z0-9]+` runs. Token-Jaccard is set-based.
- Granularities per pair: (g1) changed-sentence — minimal diff-localized sentence(s); (g2) quoted-passage — the `orig_text`/`correct_text` fields as filed; (g3) section-context — the erratum's quoted text re-located in the frozen RFC full text and expanded to its section, best-effort, with match rate disclosed; g3 failures drop from g3 only.
- Edit classes over Verified-Technical (machine-labeled, cascade-arbitrated, human-audited on 300 stratified pairs): RFC-2119 keyword-strength change (case-sensitive multiset over MUST, MUST NOT, REQUIRED, SHALL, SHALL NOT, SHOULD, SHOULD NOT, RECOMMENDED, NOT RECOMMENDED, MAY, OPTIONAL); quantity/number change (`\d+(\.\d+)?` multiset); polarity/negation; identifier/constant; scope/other.
- Encoders: the nine pinned polaritycheck configurations, checkpoint hashes carried over from the Paper A artifact, plus operating points cosine 0.30 / 0.40 / 0.60 / 0.80 / 0.85 / 0.95.

## 3. Hypotheses and numeric bars (pass/fail is per-bar, no post-hoc softening)

- **H1 (gates approve corrections).** At thresholds ≥ 0.80, ≥ 90% of Verified-Technical pairs score above threshold at g2; median Technical cosine ≥ 0.95.
- **H2 (little decision content even unconfounded).** Marginal Technical-vs-Editorial AUROC ∈ [0.45, 0.65] for all nine configurations at g2, AND overlap-decile stratification moves each configuration's estimate by < 0.05. If the second clause fails, the corpus is NOT certified naturally matched and all decision claims are reported stratified-only.
- **H3 (worst-classes replication).** Modal-keyword and quantity classes have the two highest median cosines among Technical edit classes, each ≥ 0.97, for ≥ 7 of 9 configurations.
- **H4 (calibrations do not transfer).** Each repair (per-encoder optimal threshold; logistic on cosine + token-Jaccard; NLI cross-encoder) fitted on errata drops ≥ 0.10 balanced accuracy or AUROC when frozen-evaluated on the bis corpus.
- **H5 (dilution in the wild).** Mean decision AUROC (over configurations) decays monotonically g1 → g2 → g3 with total drop ≥ 0.10.

## 4. Analysis plan

Marginal + overlap-decile-stratified AUROC per (configuration, granularity), cluster bootstrap by RFC document number (10,000 resamples, seed 20260805); balanced accuracy and firing rate at the six operating points; per-class median cosine and class AUROC; Cliff's δ + permutation test (mean-difference statistic, 20,000 permutations, seed 20260805) for the overlap-class coupling; Spearman cosine~Jaccard within class; κ (Cohen) on both annotation arms with adjudicated label-noise rate reported as a ceiling on every decision-axis claim.

## 5. Bis corpus (held-out; mined AFTER errata analysis is frozen, from a disjoint pipeline)

All obsoletes/obsoleted-by families from the frozen `rfc-index.xml`; alignment through intermediate revisions only (never skipping steps); pre-registered artifact taxonomy excluded before labeling: case normalization (`MUST not`→`MUST NOT`), prose→keyword normalization (`are permitted to`→`MAY`), subject rewording without strength change, alignment errors. Gate: ≥ 100 human-verified genuine strength transitions or the transfer arm reports "insufficient natural positives" as a finding — the gate cannot be lowered after mining begins. 200-pair two-annotator alignment audit.

## 6. Computed before this draft (disclosed, encoder-blind, all lexical)

From the frozen snapshot via `scripts/verify_snapshot.py`, as a two-source check against the 2026-08-05 independent workflow-verifier parse: entry/status/type counts; both-texts-non-empty counts per class; RFC-2119 keyword-multiset-change and number-multiset-change counts; token-Jaccard distributions per class with medians, Cliff's δ, permutation p. These informed H2's stratification clause and the H3 class choices; they involve no embedding, no cosine, no encoder.

## 7. Freeze protocol

Freezing = one commit that (a) finalizes this file with §6's actual numbers cited from `results/verification/e1_snapshot_verification.json`, (b) pins `harness/lib/filters.py`, (c) is tagged `prereg-e1`. Every subsequent change to this file is an amendment section below the tag line, never an edit above it.
