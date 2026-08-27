"""Pre-committed analysis for the cross-source construct test.

Written and committed BEFORE either annotator seat finished, so the refutation test cannot be
steered — the E3 precedent (analysis committed before observation).

THE TEST. The hostile review's strongest objection to the sign-flip law is that its four rows
come from four different label-generating processes, so the reversal may live in the labelling
rather than in the text. This script holds the label definition fixed — one span-construct rubric,
one annotator pool, 380 pairs drawn from three sources and shuffled — and recomputes the coupling.

PRE-COMMITTED READING OF THE OUTCOME (fixed here, before the data):
  * If the median token-Jaccard of the construct-CHANGING class is ABOVE the construct-PRESERVING
    class for authored, and BELOW it for bis, with errata between them, the reversal survives a
    fixed label definition. The law is a property of the text. Objection refuted.
  * If all three sources show the same orientation under the unified rubric, the reversal was an
    artifact of the labelling processes. The law must be restated as label-relative, and §3 of the
    manuscript is rewritten to say so. This outcome is reportable and will be reported.
  * Mixed or CI-overlapping outcomes are reported as inconclusive, not resolved in our favour.

Agreement between the seats is reported per source: a rubric that travels badly across registers
would show up as κ dropping in one source, and that is itself a finding about the instrument.

Recompute: python scripts/crosssource_coupling.py
Frozen:    results/verification/crosssource_coupling.json
"""
import json, random, re, statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V = ROOT / "results" / "verification"
SEED = 20260812

key = json.loads((V / "crosssource_key.json").read_text(encoding="utf-8"))["items"]
key = {int(k): v for k, v in key.items()}
packet = {it["item"]: it for it in json.loads((V / "crosssource_blind_packet.json").read_text(encoding="utf-8"))}

def load(name):
    p = V / name
    if not p.exists():
        return None
    return {j["item"]: j["verdict"] for j in json.loads(p.read_text(encoding="utf-8"))["judgments"]}

A, B = load("annotator_A_crosssource.json"), load("annotator_B_crosssource.json")
if A is None or B is None:
    raise SystemExit("both annotator seats must be committed before this analysis runs")

tok = lambda s: set(re.findall(r"[a-z0-9]+", s.lower()))
def jac(a, b):
    u = a | b
    return len(a & b) / len(u) if u else 1.0

cats = ["different", "same", "unjudgeable"]
n = len(key)
po = sum(1 for i in key if A[i] == B[i]) / n
pe = sum((sum(1 for i in key if A[i] == c) / n) * (sum(1 for i in key if B[i] == c) / n) for c in cats)
kappa = (po - pe) / (1 - pe)

out = {"n": n, "kappa_AB_overall": round(kappa, 4), "agreement_raw": round(po, 4),
       "rubric": "docs/annotation_protocol_errata.md — identical for every source",
       "note": "construct label = the two seats' agreed verdict; disagreements are excluded here and "
               "listed for operator adjudication (same discipline as the errata and bis audits)",
       "by_source": {}, "disagreements": sorted(i for i in key if A[i] != B[i])}

for src in ("authored", "errata", "bis"):
    idx = [i for i in key if key[i]["source"] == src]
    agreed = [i for i in idx if A[i] == B[i] and A[i] != "unjudgeable"]
    chg = [i for i in agreed if A[i] == "different"]
    pre = [i for i in agreed if A[i] == "same"]
    jc = [jac(tok(packet[i]["text_A"]), tok(packet[i]["text_B"])) for i in chg]
    jp = [jac(tok(packet[i]["text_A"]), tok(packet[i]["text_B"])) for i in pre]
    med_c = round(statistics.median(jc), 4) if jc else None
    med_p = round(statistics.median(jp), 4) if jp else None
    # bootstrap CI on the gap (preserving - changing): positive = aligned, negative = inverted
    gaps = []
    if jc and jp:
        rng = random.Random(SEED)
        for _ in range(10000):
            gaps.append(statistics.median([rng.choice(jp) for _ in jp])
                        - statistics.median([rng.choice(jc) for _ in jc]))
        gaps.sort()
    po_s = sum(1 for i in idx if A[i] == B[i]) / len(idx)
    pe_s = sum((sum(1 for i in idx if A[i] == c) / len(idx)) * (sum(1 for i in idx if B[i] == c) / len(idx))
               for c in cats)
    out["by_source"][src] = {
        "n_items": len(idx), "n_agreed_judgeable": len(agreed),
        "n_construct_changing": len(chg), "n_construct_preserving": len(pre),
        "median_jaccard_changing": med_c, "median_jaccard_preserving": med_p,
        "gap_preserving_minus_changing": round(med_p - med_c, 4) if (jc and jp) else None,
        "gap_ci95": [round(gaps[250], 4), round(gaps[9750], 4)] if gaps else None,
        "orientation": (None if not gaps else
                        "aligned" if gaps[250] > 0 else
                        "inverted" if gaps[9750] < 0 else "indistinguishable"),
        "kappa_within_source": round((po_s - pe_s) / (1 - pe_s), 4),
        "construct_vs_native_confusion": {
            f"native_{c}__construct_{v}": sum(1 for i in agreed
                                              if key[i]["native_class"] == c and
                                              A[i] == ("different" if v == "changing" else "same"))
            for c in ("changing", "preserving") for v in ("changing", "preserving")},
    }

ors = [out["by_source"][s]["orientation"] for s in ("authored", "errata", "bis")]
out["verdict"] = (
    "REVERSAL SURVIVES A FIXED LABEL DEFINITION — the sign-flip is a property of the text"
    if ors[0] == "inverted" and ors[2] == "aligned" else
    "NO REVERSAL UNDER A FIXED RUBRIC — the law must be restated as label-relative"
    if len(set(o for o in ors if o)) == 1 else
    f"INCONCLUSIVE — orientations {dict(zip(('authored','errata','bis'), ors))}")
(V / "crosssource_coupling.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")

print(f"kappa(A,B) overall = {out['kappa_AB_overall']}  ({len(out['disagreements'])} disagreements)")
for s in ("authored", "errata", "bis"):
    d = out["by_source"][s]
    print(f"  {s:9} changing {d['median_jaccard_changing']}  preserving {d['median_jaccard_preserving']}"
          f"  gap {d['gap_preserving_minus_changing']} {d['gap_ci95']}  -> {d['orientation']}"
          f"  (κ {d['kappa_within_source']})")
print(out["verdict"])
