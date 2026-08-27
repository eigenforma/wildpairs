"""Does the surviving claim survive its own selection effect?

THE THREAT. The cross-source test's remaining claim is that coupling MAGNITUDE differs across
natural authoring processes: errata +0.081, bis +0.331, non-overlapping CIs. But the two corpora
were not selected the same way. `harness/e1/bis_mine.py` accepts a sentence alignment only when
token-Jaccard >= 0.40 (and beats the runner-up by 0.10), so **every bis pair carries >= 0.40
overlap by construction**, while errata pairs came from the erratum's own quoted text with no
overlap filter at all. Comparing a left-truncated distribution against an untruncated one can
manufacture, inflate, or mask a magnitude difference.

THE TEST. Apply the bis floor to the errata arm and recompute both gaps on the common support.
If the errata gap moves materially, the magnitude comparison was confounded by selection and the
claim must be restated on the common support. If it holds, the claim survives its sharpest
remaining objection.

Also reported: how much of each arm the floor removes, and where the changing/preserving mass
sits relative to it, since truncation that bites one class harder is the mechanism of concern.

Recompute: python scripts/crosssource_truncation_check.py
Frozen:    results/verification/crosssource_truncation_check.json
"""
import json, random, re, statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V = ROOT / "results" / "verification"
FLOOR = 0.40
SEED = 20260812

key = {int(k): v for k, v in
       json.loads((V / "crosssource_key.json").read_text(encoding="utf-8"))["items"].items()}
packet = {it["item"]: it for it in
          json.loads((V / "crosssource_blind_packet.json").read_text(encoding="utf-8"))}
A = {j["item"]: j["verdict"] for j in
     json.loads((V / "annotator_A_crosssource.json").read_text(encoding="utf-8"))["judgments"]}
B = {j["item"]: j["verdict"] for j in
     json.loads((V / "annotator_B_crosssource.json").read_text(encoding="utf-8"))["judgments"]}

tok = lambda s: set(re.findall(r"[a-z0-9]+", s.lower()))
def jac(a, b):
    u = a | b
    return len(a & b) / len(u) if u else 1.0

def gap_ci(jc, jp, seed=SEED, n=10000):
    if not jc or not jp:
        return None, None
    rng = random.Random(seed)
    g = sorted(statistics.median([rng.choice(jp) for _ in jp])
               - statistics.median([rng.choice(jc) for _ in jc]) for _ in range(n))
    return round(statistics.median(jp) - statistics.median(jc), 4), [round(g[250], 4), round(g[9750], 4)]

out = {"floor": FLOOR,
       "why": "bis_mine.py accepts an alignment only at token-Jaccard >= 0.40; errata pairs "
              "carried no overlap filter. The comparison is otherwise between a truncated and an "
              "untruncated distribution.",
       "arms": {}}

for src in ("errata", "bis", "authored"):
    idx = [i for i in key if key[i]["source"] == src and A[i] == B[i] and A[i] != "unjudgeable"]
    rows = [(i, A[i], jac(tok(packet[i]["text_A"]), tok(packet[i]["text_B"]))) for i in idx]
    full_c = [j for _, v, j in rows if v == "different"]
    full_p = [j for _, v, j in rows if v == "same"]
    cut_c = [j for j in full_c if j >= FLOOR]
    cut_p = [j for j in full_p if j >= FLOOR]
    g_full, ci_full = gap_ci(full_c, full_p)
    g_cut, ci_cut = gap_ci(cut_c, cut_p)
    out["arms"][src] = {
        "n_full": {"changing": len(full_c), "preserving": len(full_p)},
        "n_on_common_support": {"changing": len(cut_c), "preserving": len(cut_p)},
        "removed_by_floor": {"changing": len(full_c) - len(cut_c),
                             "preserving": len(full_p) - len(cut_p)},
        "removed_frac": {"changing": round(1 - len(cut_c) / len(full_c), 4) if full_c else None,
                         "preserving": round(1 - len(cut_p) / len(full_p), 4) if full_p else None},
        "gap_full": g_full, "ci_full": ci_full,
        "gap_common_support": g_cut, "ci_common_support": ci_cut,
        "median_changing_common": round(statistics.median(cut_c), 4) if cut_c else None,
        "median_preserving_common": round(statistics.median(cut_p), 4) if cut_p else None,
    }

e, b = out["arms"]["errata"], out["arms"]["bis"]
if e["ci_common_support"] and b["ci_common_support"]:
    disjoint = (e["ci_common_support"][1] < b["ci_common_support"][0] or
                b["ci_common_support"][1] < e["ci_common_support"][0])
    out["verdict"] = (
        "MAGNITUDE DIFFERENCE SURVIVES on the common support: errata and bis gap CIs remain "
        "disjoint after the bis selection floor is applied to both arms."
        if disjoint else
        "MAGNITUDE DIFFERENCE DOES NOT SURVIVE on the common support: the CIs overlap once the "
        "bis selection floor is applied to both arms, so the difference cannot be separated from "
        "the selection effect and must not be claimed.")
else:
    out["verdict"] = "INSUFFICIENT DATA on the common support"

(V / "crosssource_truncation_check.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
for s in ("errata", "bis", "authored"):
    a = out["arms"][s]
    print(f"{s:9} full gap {a['gap_full']} {a['ci_full']}  ->  common-support gap "
          f"{a['gap_common_support']} {a['ci_common_support']}   "
          f"(floor removed {a['removed_frac']['changing']} of changing, "
          f"{a['removed_frac']['preserving']} of preserving)")
print()
print(out["verdict"])
