# Decision brief — operator rulings needed, with terms defined (2026-08-06)

Five decisions. The first three are operational; the last two are the real ones — they decide how the results speak. Each names what hinges on it.

---

## D1 — The bis audit arm (your annotation hours, and one recruit)

**Terms.** *Label precision*: the fraction of machine-labeled strength transitions that a human confirms as genuinely meaning-changing. *Negative-class leak*: rewordings that changed meaning without touching an RFC-2119 keyword — machine-labeled "preserving," actually "changing." *Label circularity*: the bis labels were assigned by a lexical rule (keyword multisets), and the logistic gate reads lexical features — labeler and instrument partially share eyes, so part of the gate's 0.71–0.74 "success" may be the rule seeing itself.

**The task.** 200 stratified pairs (`results/verification/bis_audit_sample_200.jsonl`), two annotators, blind to every hypothesis (the annotator sees the labeling protocol only — never the prereg, never this brief). Judgment per pair: does the revision change what the sentence requires? Estimated 6–10 hours per annotator.

**What you decide.** (a) Who the independent second annotator is — a human who has never seen this program's predictions, or an agent context firewalled per the contamination protocol; annotator and reviewer roles are mutually exclusive per person until annotation closes. (b) When — before paper drafting, because D4's altitude depends on it.

**What hinges.** Audit-clean, we can write "calibrations transferred onto institution-grade meaning changes." Audit-pending or audit-weak, we must write "machine-labeled transitions," and the H4 sign-flip finding keeps a circularity asterisk. The audit is the difference between a footnote and a caveat that reviewers will probe.

## D2 — Prereg amendment window (cheap, do soon)

**Terms.** The tag `prereg-e1` froze everything above its line; *amendments* file below it, dated, and anything analyzed after seeing data is labeled *post-hoc*.

**What you decide.** Whether to file the two post-hoc analyses we already ran as formal amendments: the three-regime coupling-orientation analysis (the sign-flip table) and the per-class bis Jaccard/cosine breakdown. Recommended: yes, immediately — it costs one commit and forecloses any "they quietly added analyses" reading. Nothing else needs amending; the failed bars stay exactly as failed.

## D3 — Outreach sends (ready; your addresses and your send button)

All five drafts in `Falsifyer/docs/outreach/paper_b_outreach.md` can now carry the completed scorecard. **What you decide:** (a) resolve the ⟨VERIFY⟩ addresses (McQuistin, Weller, Blanco/Hossain); (b) whether the McQuistin note adds one sentence on the H4 sign-flip — recommended: yes; "your community's two revision processes couple wording to meaning with opposite signs" is the single most interesting sentence we can offer a standards-process scholar; (c) send order and dates. Reply expectations stay 1–2 engaged from five.

## D4 — Claim altitude for Paper B (the real question)

> **RULED 2026-08-06: HOLD FOR E2.** The altitude decision defers until the dilution titration delivers (or refutes) the second law. Drafting waits; E1 results stay frozen; outreach proceeds (the emails share prereg + scorecard and commit no altitude). E2 is now the program's critical path.

**Terms.** *Claim altitude* is how far above the raw evidence the headline sits. Three rungs are available, all now evidenced:

1. **Audit altitude** (lowest, safest): *"Shipped similarity gates approve 89–98% of corrections the IETF's own verifiers ruled meaning-changing; no encoder distinguishes the classes better than 0.52 stratified AUROC."* Unassailable; institution-labeled; already survived its own bars' scrutiny.
2. **Law altitude** (the discovery): *"The wording–meaning coupling changes sign across natural authoring processes"* — inverted (authored corpora), near-zero (corrections), aligned (revisions). Therefore a calibrated gate in a new authoring context is **uncontrolled**, not merely degraded. This is §7 upgraded from magnitude-instability to sign-instability, and it explains all three papers' regimes with one object.
3. **Instrument altitude** (the arc-closer): *"Natural editing processes produce overlap-matched audit corpora that authored corpora cannot"* — the errata benchmark and bis corpus released as the field's standardized instruments; Paper A's abstract hanger answered: the instrument now exists; the gate still does not.

**What you decide.** Which rung is the headline. My recommendation: lead with 1 (the spotlight), make 2 the spine (the law the evidence converges on), close on 3 (the released instruments + the hanger's answer). That mirrors Paper A's deployed-result → mechanism → artifact structure. But this is a voice-and-identity ruling, not a technical one — it is yours. Note: the E2 dilution results, when they land, slot into rung 2 as the second law (signal decay with length); if you want one paper carrying both laws, the abstract leads differently than if E2 becomes its own release.

## D5 — The figures program (your commission + my independent reach)

Your commissioned image — the grid of physically drawn semantic flowstructures — has a demonstration artifact accompanying this brief: primitives legend first, then the phenomena rendered in the vernacular, built to earn your "yes, that's the object" before any scale-up. **What you decide:** whether the vernacular as demonstrated is the one; corrections to the primitive set are cheapest now.

My independent picks (not needing rulings, listed for visibility): the three-regime orientation diagram (one figure, whole H4 story); the threshold-ceiling figure (nine fitted cutoffs pinned at 0.990–0.997 against both class distributions — the "nothing to cut" picture); the honest scorecard as a graphic (pass/fallback/fail marks against pre-registered bars — credibility as a figure); E2's L* decay curves when the titration runs.

---

*Sequenced: D2 today (one commit), D5's ruling when the demonstration convinces you, D1 scheduling this week (it gates D4's final wording), D3 sends when addresses resolve, D4 before drafting begins.*
