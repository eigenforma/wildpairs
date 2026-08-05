# wildpairs

**Private during development. Working name — the pairs come from the wild, authored by nobody for this audit.**

Corpus, harness, and frozen results for the empirical follow-up to *Similarity Gates Approve Reversals: A Validity Audit of Embedding-Cosine Thresholds in Agent Systems* (Frias, 2026; artifact: [eigenforma/polaritycheck](https://github.com/eigenforma/polaritycheck), DOI 10.5281/zenodo.21796531).

Two experiments:

- **E1 — The Institution Flagged It.** Cosine gates audited against 25 years of IETF-verified errata corrections: minimal edits the RFC Editor's own process ruled Technical (meaning-changing) or Editorial (meaning-preserving). Institutional labels, naturally overlap-matched classes, held-out transfer to bis-revision requirement-strength changes.
- **E2 — The Dilution Law.** The flip-vs-faithful decision signal as a measured function of passage length: CondaQA crowd-authored payloads in byte-identical real host passages, titrated 64→4096 tokens, with the per-encoder critical length L* at which every shipped operating point goes blind.

Start here:

- [PLAN.md](PLAN.md) — the live execution program, phase matrices, swarm job assignments, execution log.
- [docs/experiments.md](docs/experiments.md) — full experiment specifications, hypotheses with numeric bars, dataset provenance, adversarial novelty/feasibility verification record.
- [PREREGISTRATION_E1.md](PREREGISTRATION_E1.md) — E1 pre-registration (DRAFT until frozen by tag `prereg-e1`; no encoder output observed on any errata pair before that tag).
- [RUNBOOK.md](RUNBOOK.md) — exact operator command triggers for the three lab systems.

Discipline inherited from the Paper A program: freeze-first corpora with SHA-256 manifests, encoder-blind construction, pre-registered predictions with numeric bars, two-source verification of load-bearing counts, no caps in counting scripts, results as frozen JSON that the prose can only cite, never source.

No LICENSE yet — operator decision, blocking release, not development.
