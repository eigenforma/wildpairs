"""Population-reweighted promoted-primary AUROC (follow-up named in
docs/findings_errata_audit_2026-08-11.md): the audited 300 were stratified (T balanced
50/50/50 over kw2119/number/other; E uniform 150), so sample-frame AUROCs are not
population estimates. Reweight each item by pool_size/sample_size for its stratum
(pools: kw2119 118, number 475, other 832, Editorial 1,402 — Verified-prose g1) and
compute weighted AUROC under construct labels. Post-hoc, primary per the A5 trigger.

Recompute: python scripts/reweighted_primary_auroc.py
Frozen:    results/verification/promoted_primary_auroc_reweighted.json
"""
import json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V = ROOT / "results" / "verification"

A = {j["item"]: j["verdict"] for j in json.loads((V / "annotator_A_errata.json").read_text(encoding="utf-8"))["judgments"]}
B = {j["item"]: j["verdict"] for j in json.loads((V / "annotator_B_errata.json").read_text(encoding="utf-8"))["judgments"]}
adj = {int(k): v for k, v in json.loads((V / "errata_adjudication_answers.json").read_text(encoding="utf-8"))["verdicts"].items()}
verdict = {i: (A[i] if A[i] == B[i] else adj[i]) for i in range(300)}
key = {int(k): v for k, v in json.loads((V / "errata_audit_key.json").read_text(encoding="utf-8"))["items"].items()}
sample = {r["item"]: r for r in (json.loads(l) for l in
          (V / "errata_audit_sample_300.jsonl").read_text(encoding="utf-8").splitlines() if l.strip())}

POOL = {"kw2119": 118, "number": 475, "other": 832, "editorial-na": 1402}
SAMP = {"kw2119": 50, "number": 50, "other": 50, "editorial-na": 150}
w = {i: POOL[key[i]["edit_class"]] / SAMP[key[i]["edit_class"]] for i in range(300)}

items = [i for i in range(300) if verdict[i] != "unjudgeable"]
pos = [i for i in items if verdict[i] == "different"]
neg = [i for i in items if verdict[i] == "same"]

def wauroc(score):
    num = den = 0.0
    for p in pos:
        for q in neg:
            if p not in score or q not in score:
                continue
            ww = w[p] * w[q]
            den += ww
            num += ww if score[p] < score[q] else (0.5 * ww if score[p] == score[q] else 0.0)
    return round(num / den, 4) if den else None

tok = lambda s: set(re.findall(r"[a-z0-9]+", s.lower()))
def jac(a, b):
    u = a | b
    return len(a & b) / len(u) if u else 1.0

out = {"note": "population-reweighted (Verified-prose g1 frame); construct labels; post-hoc, "
               "primary per A5 trigger; weights = pool/sample per stratum",
       "weighted_class_shares": {
           "changing": round(sum(w[i] for i in pos) / sum(w[i] for i in items), 4),
           "preserving": round(sum(w[i] for i in neg) / sum(w[i] for i in items), 4)},
       "configs": {}}
for f in sorted((ROOT / "results" / "e1_sweep").glob("*.json")):
    d = json.loads(f.read_text(encoding="utf-8"))
    out["configs"][d["config"]] = {
        g: wauroc({i: d["granularities"][g][sample[i]["pair_id"]]
                   for i in items if sample[i]["pair_id"] in d["granularities"][g]})
        for g in ("g1", "g2")}
out["jaccard_baseline_g1"] = wauroc({i: jac(tok(sample[i]["g1_orig"]), tok(sample[i]["g1_corr"])) for i in items})

(V / "promoted_primary_auroc_reweighted.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
print("weighted class shares:", out["weighted_class_shares"])
print("Jaccard baseline g1:", out["jaccard_baseline_g1"])
for k, v in sorted(out["configs"].items(), key=lambda kv: kv[1]["g1"]):
    print(f"  g1 {v['g1']:.4f}  g2 {v['g2']:.4f}  {k}")
