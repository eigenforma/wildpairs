"""Cross-source construct packet — the refutation test for the "it's a labelling convention"
objection against the sign-flip law.

The objection (2026-08-12 hostile review, finding 2): the four regime rows come from different
label-generating processes, so the coupling's sign reversal may be a property of the labels, not
of the text. It is the strongest attack on the paper's lead claim, and the manuscript concedes
the mechanism while still asserting a property of the world.

The refutation, if it survives: apply ONE rubric — `docs/annotation_protocol_errata.md`'s
span-level construct question — through ONE annotator pool to samples from every source, then
recompute the coupling under those unified labels. If the orientation still reverses when the
label definition is held fixed, the flip is in the text, not the labelling.

Sample (seed 20260812, stratified within each source by its native class so both arms are
represented, then all sources shuffled together and source-blinded):
  authored : all 80 pairs of the Paper A factorial instrument (the corpus is only 80)
  errata   : 150 Verified-prose pairs
  bis      : 150 mined revision pairs
Outputs: crosssource_blind_packet.json (annotator-facing: item, text_A, text_B only)
         crosssource_key.json          (SEALED: source, native label, A/B order, pair id)
"""
import json, random, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V = ROOT / "results" / "verification"
PAPER_A = Path(r"C:\Users\poeti\cosine-threshold-finding\corpus")
SEED = 20260812
rng = random.Random(SEED)

items = []

# ── authored: Paper A's factorial instrument (native class = decision OPPOSITE/SAME) ──
for f in ("distinctness_2x2.jsonl", "constraint_2x2.jsonl"):
    for line in (PAPER_A / f).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        # the two tasks carry different label vocabularies: distinctness is OPPOSITE/SAME,
        # constraint is VIOLATION/FAITHFUL. Both changing-arms must map to "changing" —
        # reading only the first pair silently files 20 violations as preserving.
        CHANGING = {"OPPOSITE", "VIOLATION"}
        PRESERVING = {"SAME", "FAITHFUL"}
        assert r["decision"] in CHANGING | PRESERVING, f"unmapped decision label {r['decision']!r}"
        items.append({"source": "authored", "pair_id": r["id"],
                      "native_class": "changing" if r["decision"] in CHANGING else "preserving",
                      "native_label": r["decision"], "a": r["text_a"], "b": r["text_b"]})

# ── errata: Verified prose, stratified over the institutional Technical/Editorial split ──
er = [json.loads(l) for l in (ROOT / "corpus" / "e1_errata" / "pairs_g1g2.jsonl")
      .read_text(encoding="utf-8").splitlines() if l.strip()]
er = [r for r in er if r["status"] == "Verified" and not r["code_primary"]
      and r["g1_orig"].strip() and r["g1_corr"].strip()]
for cls, want in (("Technical", 75), ("Editorial", 75)):
    pool = sorted([r for r in er if r["type"] == cls], key=lambda r: r["pair_id"])
    for r in rng.sample(pool, want):
        items.append({"source": "errata", "pair_id": r["pair_id"],
                      "native_class": "changing" if cls == "Technical" else "preserving",
                      "native_label": cls, "a": r["g1_orig"], "b": r["g1_corr"]})

# ── bis: mined revisions, stratified over the machine strength/reworded split ──
bis = [json.loads(l) for l in (ROOT / "corpus" / "e1_errata" / "bis_pairs.jsonl")
       .read_text(encoding="utf-8").splitlines() if l.strip()]
for lab, want in (("strength_transition", 75), ("keyword_preserved_rewording", 75)):
    pool = sorted([r for r in bis if r["label"] == lab], key=lambda r: r["pair_id"])
    for r in rng.sample(pool, want):
        items.append({"source": "bis", "pair_id": r["pair_id"],
                      "native_class": "changing" if lab == "strength_transition" else "preserving",
                      "native_label": lab, "a": r["old_sentence"], "b": r["new_sentence"]})

rng.shuffle(items)
packet, key = [], {}
for i, it in enumerate(items):
    flip = rng.random() < 0.5
    ta, tb = (it["b"], it["a"]) if flip else (it["a"], it["b"])
    packet.append({"item": i, "text_A": ta, "text_B": tb})
    key[i] = {"source": it["source"], "pair_id": it["pair_id"],
              "native_class": it["native_class"], "native_label": it["native_label"],
              "A_is": "second" if flip else "first"}

(V / "crosssource_blind_packet.json").write_text(json.dumps(packet, indent=1), encoding="utf-8")
(V / "crosssource_key.json").write_text(json.dumps(
    {"seed": SEED, "rubric": "docs/annotation_protocol_errata.md (span-level construct, identical for every source)",
     "purpose": "refutation test for the labelling-convention objection to the sign-flip law",
     "n_by_source": {s: sum(1 for v in key.values() if v["source"] == s) for s in ("authored", "errata", "bis")},
     "items": key}, indent=1), encoding="utf-8")
from collections import Counter
print("packet:", len(packet), "items |", dict(Counter(v["source"] for v in key.values())))
print("native class balance:", dict(Counter((v["source"], v["native_class"]) for v in key.values())))
