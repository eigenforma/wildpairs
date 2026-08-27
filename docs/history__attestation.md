# History attestation

The public history of this repository is curated, and this file records the curation, because the history is part of the evidence: the four preregistration tags below carry the paper's claim that every numeric bar was frozen before any encoder scored a pair.

| tag | commit | frozen | scope |
|---|---|---|---|
| prereg-e1 | 2a3618c | 2026-08-05 | E1, the institutional audit |
| prereg-e3 | d633e5b | 2026-08-07 | E3, the validity ladder |
| prereg-e4 | 5b359fd | 2026-08-11 | E4, the geometric floor survey |
| prereg-e2 | a47cb6a | 2026-08-11 | E2, the length titration |

Two curation events:

1. **2026-08-12.** The working history around the freeze period was curated, and all four tags kept their original commits. Recorded at the time.
2. **2026-08-27, this release.** The editorial period after the last tag, 53 commits of manuscript drafting and correction rounds, was squashed into the single release commit, and internal working documents (draft versions, interim findings notes, planning and operations files) left the tree. All four tags and their full ancestry are byte-identical originals.

Nothing quantitative moved in either event. Every headline number recomputes from the frozen results with `python scripts/recompute_headline_numbers.py` (65 of 65 PASS). Dated records kept in this repository, the corrections ledger and the scope freeze among them, may cite working documents by name; those documents live in the author's complete private archive, which is retained and available to reviewers on request.
