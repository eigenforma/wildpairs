# Data, corpora, and prose — licence terms

Ratified 2026-08-24. Code is MIT (see [LICENSE](LICENSE)). This file covers everything else, and
follows the split already used by the companion artifact
[eigenforma/polaritycheck](https://github.com/eigenforma/polaritycheck): permissive code,
attribution-licensed data, third-party sources under their own terms.

## 1. Our own material — CC BY 4.0

Copyright (c) 2026 Scott E. Frias (Eigenforma / Freemind Labs), licensed under
[Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/).

This covers everything authored here: the pre-registrations, `PLAN.md`, `RUNBOOK.md`, the design
and findings documents under `docs/`, every file under `results/` (scores, fits, verdicts,
annotator judgments, ledgers), and the derived structures in `corpus/` — pair alignments, edit-class
labels, granularity extractions, anchor sets, and manifests — as distinct from the third-party text
they carry.

## 2. Third-party text redistributed in this repository

Only the files listed here contain text this project did not write. Each stays under its own
source terms; nothing in §1 extends to it.

| file | source | terms |
|---|---|---|
| `corpus/e1_errata/errata.json` | RFC Editor errata database, `https://www.rfc-editor.org/errata.json`, frozen 2026-08-05 | IETF Trust Legal Provisions (TLP) / BCP 78. Redistributed unmodified with attribution, per TLP §3.c.iii. |
| `corpus/e1_errata/pairs_g1g2.jsonl`, `pairs_g3.jsonl` | excerpts of RFC text and errata `orig_text` / `correct_text` fields | TLP / BCP 78, as attributed excerpts. The surrounding alignment, granularity, and class fields are ours (§1). |
| `corpus/e1_errata/bis_pairs.jsonl` | sentence excerpts from RFC and bis-revision documents | TLP / BCP 78, as attributed excerpts. Labels and alignments are ours (§1). |
| `corpus/e2_dilution/condaqa_{train,dev,test}.json` | CondaQA (Ravichander et al., EMNLP 2022) | Apache-2.0, redistributed with this notice. |
| `corpus/e2_dilution/anchors_frozen.jsonl` | anchor sets derived from CondaQA passages | Apache-2.0 for the CondaQA text; the anchor selection and slot identification are ours (§1). |
| `corpus/e3_composed_sweep_sample.jsonl` | 4,000 pairs each from SNLI, MultiNLI, QQP, and PAWS-Wiki | each under its own source terms — see §4. |

**Two provenance flags carried from the 2026-08-08 review, and they travel with any reuse:**

1. `correct_text` in the errata database is the *reporter's proposed* correction as verified by the
   RFC stream, not always the text that reached a later RFC. Anyone reusing these pairs as ground
   truth inherits that distinction.
2. RFCs published before RFC 5378 (pre-2008) carry different contributor grants. Pairs drawn from
   them are flagged in the corpus and should be treated as excerpt-only.

## 3. Text this project does NOT redistribute

By commitment in `PREREGISTRATION_E2.md` §2, and following the companion paper's precedent:

- **Spliced RFC host passages** (the E2 stimuli) ship as SHA-256 checksums and a deterministic
  regeneration script, never as text. See `corpus/e2_dilution/REGENERATION.md`.
- **Wikipedia host pools** (enwiki-20210701, CC BY-SA 3.0/4.0) ship the same way.
- **PubMed Central Open Access** host material (CC BY subset) ships the same way; the frozen slice
  is identified by checksum in `corpus/MANIFEST.json`.
- Full source archives for SNLI, MultiNLI, QQP, and PAWS are named in the manifest by URL and
  SHA-256; they are not copied here.

## 4. Source terms for the E3 sample

`corpus/e3_composed_sweep_sample.jsonl` carries verbatim sentence pairs. Reuse under the source
terms, not ours:

- **SNLI** — Stanford NLI corpus, CC BY-SA 4.0 (Bowman et al., 2015).
- **MultiNLI** — mixed-genre corpus with per-genre source terms, distributed for research use
  (Williams et al., 2018).
- **QQP** — Quora Question Pairs, released by Quora for non-commercial research; obtained through
  the GLUE distribution. **Attribution to Quora is required and commercial reuse is not granted.**
- **PAWS-Wiki** — Google Research; the underlying sentences are Wikipedia-derived and carry
  CC BY-SA (Zhang et al., 2019).

## 5. How to cite

See `CITATION.cff`. The companion paper is Frias (2026), *Similarity Gates Approve Reversals: A
Validity Audit of Embedding-Cosine Thresholds in Agent Systems*, arXiv:2608.10216.
