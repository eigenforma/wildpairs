"""A5 promoted-primary analysis: the adjudication trigger fired (editorial construct
disagreement 66% > 15%), so the adjudicated-construct 300-subsample becomes the primary
decision corpus. Per-config decision AUROC under CONSTRUCT labels (adjudicated
meaning-changing vs meaning-preserving), computed from the FROZEN E1 sweep cosines —
no encoder runs; this is a re-labeling of already-frozen scores, post-hoc by definition
and labeled so.

Convention: decision AUROC = P(cos_changing < cos_preserving) (+ half ties) — the
probability the gate's score ranks a meaning change as less similar than a faithful edit.
Cluster bootstrap by RFC document (1,000 resamples, seed 20260805). Jaccard-alone baseline
(pinned tokenizer, g1 texts) computed on the identical subsample.

Output: results/verification/promoted_primary_auroc.json
"""
import json, random, re, statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V = ROOT / "results" / "verification"

A = {j["item"]: j["verdict"] for j in json.loads((V / "annotator_A_errata.json").read_text(encoding="utf-8"))["judgments"]}
B = {j["item"]: j["verdict"] for j in json.loads((V / "annotator_B_errata.json").read_text(encoding="utf-8"))["judgments"]}
adj = {int(k): v for k, v in json.loads((V / "errata_adjudication_answers.json").read_text(encoding="utf-8"))["verdicts"].items()}
verdict = {i: (A[i] if A[i] == B[i] else adj[i]) for i in range(300)}

rows = [json.loads(l) for l in (V / "errata_audit_sample_300.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
sample = {r["item"]: r for r in rows}

items = [i for i in range(300) if verdict[i] != "unjudgeable"]
pos = [i for i in items if verdict[i] == "different"]   # construct: meaning-changing
neg = [i for i in items if verdict[i] == "same"]

tok = lambda s: set(re.findall(r"[a-z0-9]+", s.lower()))
def jac(a, b):
    u = a | b
    return len(a & b) / len(u) if u else 1.0

def auroc(score):  # score: item -> similarity-like value; changing should score LOWER
    ps = [score[i] for i in pos if i in score]
    ns = [score[i] for i in neg if i in score]
    if not ps or not ns:
        return None
    w = 0.0
    for p in ps:
        for q in ns:
            w += 1.0 if p < q else (0.5 if p == q else 0.0)
    return w / (len(ps) * len(ns))

def cluster_ci(score, nboot=1000, seed=20260805):
    rng = random.Random(seed)
    docs = sorted({sample[i]["doc_id"] for i in items})
    by_doc = {d: [i for i in items if sample[i]["doc_id"] == d] for d in docs}
    vals = []
    for _ in range(nboot):
        pick = [i for d in (rng.choice(docs) for _ in docs) for i in by_doc[d]]
        ps = [score[i] for i in pick if verdict[i] == "different" and i in score]
        ns = [score[i] for i in pick if verdict[i] == "same" and i in score]
        if not ps or not ns:
            continue
        w = sum((1.0 if p < q else (0.5 if p == q else 0.0)) for p in ps for q in ns)
        vals.append(w / (len(ps) * len(ns)))
    vals.sort()
    return [round(vals[int(0.025 * len(vals))], 4), round(vals[int(0.975 * len(vals))], 4)]

out = {"n_judgeable": len(items), "n_changing": len(pos), "n_preserving": len(neg),
       "note": "post-hoc by construction (labels adjudicated 2026-08-11 after the frozen sweep); "
               "primary per the A5 promotion trigger; cluster bootstrap by RFC doc, seed 20260805",
       "configs": {}}

for f in sorted((ROOT / "results" / "e1_sweep").glob("*.json")):
    d = json.loads(f.read_text(encoding="utf-8"))
    for g in ("g1", "g2"):
        scores = {i: d["granularities"][g][sample[i]["pair_id"]]
                  for i in items if sample[i]["pair_id"] in d["granularities"][g]}
        a = auroc(scores)
        out["configs"].setdefault(d["config"], {})[g] = {
            "auroc": round(a, 4), "ci95_cluster": cluster_ci(scores), "n": len(scores)}

jacc = {i: jac(tok(sample[i]["g1_orig"]), tok(sample[i]["g1_corr"])) for i in items}
out["jaccard_baseline_g1"] = {"auroc": round(auroc(jacc), 4), "ci95_cluster": cluster_ci(jacc)}

(V / "promoted_primary_auroc.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
g1s = sorted((v["g1"]["auroc"], k) for k, v in out["configs"].items())
print(f"n={len(items)} ({len(pos)} changing / {len(neg)} preserving)")
print("Jaccard baseline g1:", out["jaccard_baseline_g1"]["auroc"], out["jaccard_baseline_g1"]["ci95_cluster"])
for a, k in g1s:
    print(f"  g1 {a:.4f}  g2 {out['configs'][k]['g2']['auroc']:.4f}  {k}")
