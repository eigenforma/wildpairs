"""E3 analysis — the executable form of PREREGISTRATION_E3 §5, committed before any result
was observed. Scores HE3-1..HE3-5 against the frozen bars.

Per (config, source): naive AUROC; overlap-decile stratified AUROC (deciles of Jaccard within
source, strata containing both classes, weighted by pair count); caliper-matched AUROC (greedy
1:1 two-pointer match on Jaccard within 0.05, seed 20260805 for order ties); balanced accuracy
at the six operating points; bootstrap CIs (10,000 resamples, seed 20260805) on the naive and
caliper AUROCs. Artifact share = naive - caliper.
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
SWEEP = ROOT / "results" / "e3_sweep"
SAMPLE = ROOT / "corpus" / "e3_composed_sweep_sample.jsonl"
OUT = ROOT / "results" / "e3_analysis.json"

OPS = [0.30, 0.40, 0.60, 0.80, 0.85, 0.95]
SOURCES = ["paws", "qqp", "snli", "mnli"]
N_BOOT = 10_000
SEED = 20260805


def auroc(pos, neg):
    """P(score_pos > score_neg) with tie=0.5; here 'pos'=break should score LOWER cosine,
    so decision AUROC uses -cosine as the break-detection score."""
    x = np.concatenate([pos, neg])
    r = np.empty(len(x))
    order = np.argsort(x, kind="mergesort")
    sx = x[order]
    ranks = np.empty(len(x))
    i = 0
    while i < len(sx):
        j = i
        while j + 1 < len(sx) and sx[j + 1] == sx[i]:
            j += 1
        ranks[i:j + 1] = (i + j) / 2 + 1
        i = j + 1
    r[order] = ranks
    rp = r[: len(pos)]
    return (rp.sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))


def dec_auroc(cos_break, cos_pres):
    """Break-detection AUROC: break pairs should have LOWER cosine -> use negated cosine."""
    return auroc(-cos_break, -cos_pres)


def stratified(cos_b, j_b, cos_p, j_p):
    allj = np.concatenate([j_b, j_p])
    qs = np.quantile(allj, np.linspace(0, 1, 11))
    total_w, acc = 0, 0.0
    for lo, hi in zip(qs[:-1], qs[1:]):
        mb = (j_b >= lo) & (j_b <= hi)
        mp = (j_p >= lo) & (j_p <= hi)
        if mb.sum() >= 5 and mp.sum() >= 5:
            w = mb.sum() + mp.sum()
            acc += w * dec_auroc(cos_b[mb], cos_p[mp])
            total_w += w
    return acc / total_w if total_w else float("nan")


def caliper(cos_b, j_b, cos_p, j_p, tol=0.05):
    rng = np.random.default_rng(SEED)
    pb, pp = rng.permutation(len(j_b)), rng.permutation(len(j_p))
    ob = pb[np.argsort(j_b[pb], kind="mergesort")]
    op = pp[np.argsort(j_p[pp], kind="mergesort")]
    jb, jp = j_b[ob], j_p[op]
    ib = ip = 0
    keep_b, keep_p = [], []
    while ib < len(jb) and ip < len(jp):
        d = jb[ib] - jp[ip]
        if abs(d) <= tol:
            keep_b.append(ob[ib]); keep_p.append(op[ip]); ib += 1; ip += 1
        elif d > tol:
            ip += 1
        else:
            ib += 1
    if len(keep_b) < 30:
        return float("nan"), len(keep_b)
    return dec_auroc(cos_b[np.array(keep_b)], cos_p[np.array(keep_p)]), len(keep_b)


def boot_ci(fn, cos_b, cos_p, rng):
    vals = np.empty(N_BOOT)
    nb, npr = len(cos_b), len(cos_p)
    for k in range(N_BOOT):
        vals[k] = fn(cos_b[rng.integers(0, nb, nb)], cos_p[rng.integers(0, npr, npr)])
    return [round(float(np.quantile(vals, q)), 4) for q in (0.025, 0.975)]


def main():
    rows = [json.loads(l) for l in SAMPLE.read_text(encoding="utf-8").splitlines() if l.strip()]
    report = {"configs": {}, "hypotheses": {}}
    per_cfg = {}
    for f in sorted(SWEEP.glob("*.json")):
        d = json.loads(f.read_text())
        cos = np.array(d["cos"], dtype=np.float64)
        assert len(cos) == len(rows), f"{f.name}: {len(cos)} vs {len(rows)}"
        cfg = d["config"]
        entry = {}
        rng = np.random.default_rng(SEED)
        for src in SOURCES:
            idx_b = [i for i, r in enumerate(rows) if r["source"] == src and r["label"] == "break"]
            idx_p = [i for i, r in enumerate(rows) if r["source"] == src and r["label"] == "preserve"]
            cb, cp = cos[idx_b], cos[idx_p]
            jb = np.array([rows[i]["jaccard"] for i in idx_b])
            jp = np.array([rows[i]["jaccard"] for i in idx_p])
            naive = dec_auroc(cb, cp)
            strat = stratified(cb, jb, cp, jp)
            cal, n_matched = caliper(cb, jb, cp, jp)
            ba = {}
            for t in OPS:
                tpr = float((cb < t).mean())  # break flagged when cosine below cut
                tnr = float((cp >= t).mean())
                ba[str(t)] = round((tpr + tnr) / 2, 4)
            entry[src] = {
                "auroc_naive": round(float(naive), 4),
                "auroc_naive_ci": boot_ci(dec_auroc, cb, cp, rng),
                "auroc_stratified": round(float(strat), 4),
                "auroc_caliper": round(float(cal), 4) if cal == cal else None,
                "caliper_matched_pairs": n_matched,
                "artifact_share": round(float(naive - cal), 4) if cal == cal else None,
                "balanced_accuracy": ba,
            }
        per_cfg[cfg] = entry
        report["configs"][cfg] = entry

    cfgs = list(per_cfg)
    he31 = {s: sum(1 for c in cfgs if (per_cfg[c][s]["artifact_share"] or 0) >= 0.10) for s in ("qqp", "snli", "mnli")}
    report["hypotheses"]["HE3-1"] = {"bar": "artifact share >= 0.10 on each aligned source for >= 7/9 configs",
                                     "configs_meeting": he31, "pass": all(v >= 7 for v in he31.values())}
    he32 = sum(1 for c in cfgs if per_cfg[c]["qqp"]["auroc_naive"] >= 0.80)
    report["hypotheses"]["HE3-2"] = {"bar": "naive QQP AUROC >= 0.80 for >= 5/9", "n": he32, "pass": he32 >= 5}
    prod = next((c for c in cfgs if "PRODUCTION" in c), None)
    paws_ok = all(0.50 <= per_cfg[c]["paws"]["auroc_naive"] <= 0.75 for c in cfgs)
    he33 = {"all_in_range": paws_ok,
            "production_le_0.62": per_cfg[prod]["paws"]["auroc_naive"] <= 0.62 if prod else None}
    report["hypotheses"]["HE3-3"] = {"bar": "PAWS AUROC in [0.50,0.75] all; production <= 0.62",
                                     **he33, "pass": paws_ok and bool(he33["production_le_0.62"])}
    viol = [(c, s, t) for c in cfgs for s in SOURCES for t, v in per_cfg[c][s]["balanced_accuracy"].items()
            if t in ("0.8", "0.85", "0.95") and v > 0.70]
    report["hypotheses"]["HE3-4"] = {"bar": "BA <= 0.70 at {0.80,0.85,0.95} in every cell",
                                     "violations": len(viol), "sample": viol[:5], "pass": not viol}
    he35 = 0
    for c in cfgs:
        a = {s: per_cfg[c][s]["auroc_naive"] for s in SOURCES}
        if a["qqp"] > a["snli"] >= a["mnli"] > a["paws"] or a["qqp"] > a["mnli"] >= a["snli"] > a["paws"]:
            he35 += 1
    report["hypotheses"]["HE3-5"] = {"bar": "naive AUROC rank follows coupling (qqp > snli~mnli > paws) for >= 7/9",
                                     "n": he35, "pass": he35 >= 7}
    OUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["hypotheses"], indent=2))
    for c in cfgs:
        line = "  ".join(f"{s}:{per_cfg[c][s]['auroc_naive']:.3f}/{(per_cfg[c][s]['auroc_caliper'] or float('nan')):.3f}" for s in SOURCES)
        print(f"{c[:48]:48s} {line}")


if __name__ == "__main__":
    main()
