# wildpairs

**The pairs come from the wild: authored by nobody for this audit.**

Corpus, harness, and frozen results for *The Gate Stopped Deciding: Embedding-Cosine Meaning Gates on Institutional Labels and at Deployment Length* (Frias, 2026), the empirical follow-up to *Similarity Gates Approve Reversals: A Validity Audit of Embedding-Cosine Thresholds in Agent Systems* (Frias, 2026; arXiv:2608.10216; artifact: [eigenforma/polaritycheck](https://github.com/eigenforma/polaritycheck), DOI 10.5281/zenodo.21796531).

Two experiments:

- **E1 — The Institution Flagged It.** Cosine gates audited against 25 years of IETF-verified errata corrections: minimal edits the RFC Editor's own process ruled Technical (meaning-changing) or Editorial (meaning-preserving). Institutional labels, naturally overlap-matched classes, held-out transfer to bis-revision requirement-strength changes.
- **E2 — The Dilution Law.** The flip-vs-faithful decision signal as a measured function of passage length: CondaQA crowd-authored payloads in byte-identical real host passages, titrated 64→4096 tokens, with the per-encoder critical length L* at which every shipped operating point goes blind.

## Verify the paper

- The manuscript is [docs/paper_b_draft_v3.md](docs/paper_b_draft_v3.md); the arXiv source and compiled PDF sit in [docs/arxiv/](docs/arxiv/).
- Every headline number recomputes from the frozen artifacts with one command: `python scripts/recompute_headline_numbers.py` (65 of 65 PASS). Bar arithmetic derives from [results/verification/bar_ledger.json](results/verification/bar_ledger.json); the human-readable ledger is [docs/bar_ledger.md](docs/bar_ledger.md).
- All four experiments were pre-registered under freeze tags before any encoder scored a pair: `prereg-e1` (2026-08-05), `prereg-e3` (2026-08-07), `prereg-e4` and `prereg-e2` (2026-08-11). Amendments are append-only inside the PREREGISTRATION files. The public history is curated, and [docs/history_attestation.md](docs/history_attestation.md) records how; the tags and their ancestry are byte-identical originals.
- Every characterization of another paper was checked against its primary source; the audit trail is [docs/reference_verification.md](docs/reference_verification.md).

## Layout

- `corpus/` — frozen inputs with SHA-256 manifests; text this repository cannot redistribute ships as checksums plus regeneration routes.
- `harness/` — the E1–E4 experiment code; `scripts/` — verification, freezing, and build tooling.
- `results/` — frozen outputs, including the verification records in `results/verification/`. The JSON wins; prose only cites it.
- `docs/` — the manuscript, the arXiv build, figure sources, the annotation protocols, and the dated method records (the corrections ledger, the scope freeze).

Discipline inherited from the Paper A program: freeze-first corpora with SHA-256 manifests, encoder-blind construction, pre-registered predictions with numeric bars, two-source verification of decisive counts, no caps in counting scripts, results as frozen JSON that the prose can only cite, never source.

**Licence.** Code is [MIT](LICENSE). Authored corpora, annotations, and frozen measurement records
are CC BY 4.0. Redistributed third-party text — IETF errata and RFC excerpts, CondaQA, and the E3
sentence sample — stays under its source terms, listed file by file in [LICENSE-DATA.md](LICENSE-DATA.md).
Spliced RFC passages, Wikipedia host pools, and the PMC slice are not redistributed; they ship as
checksums and regeneration routes.

**Cite.** [![DOI](https://zenodo.org/badge/1324314293.svg)](https://doi.org/10.5281/zenodo.22132407) [CITATION.cff](CITATION.cff). Version DOI for v1.0.0: [10.5281/zenodo.22132408](https://doi.org/10.5281/zenodo.22132408); concept DOI for all versions: [10.5281/zenodo.22132407](https://doi.org/10.5281/zenodo.22132407).
