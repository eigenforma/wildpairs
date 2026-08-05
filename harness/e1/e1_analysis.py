"""E1 analysis: scores the frozen sweep against the prereg-e1 hypotheses H1-H5.

COMMITTED BEFORE ANY SWEEP RESULT WAS OBSERVED (verify: this file's first commit
predates results/e1_sweep/*.json in git history; the sweep was mid-flight, zero
configurations complete, when this was written). The analysis plan is prereg section 4;
this file is its executable form. H4 (bis transfer) awaits the E1-P6 corpus and is
reported as PENDING.

Population: primary = Verified prose; sensitivity = Held prose and the code stratum,
reported separately, never pooled. Decision direction: a meaning-changing (Technical)
pair should score LOWER cosine, so decision AUROC = P(cos_T < cos_E) (ties 0.5).

Outputs results/e1_analysis.json and prints the hypothesis scorecard.
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
SWEEP = ROOT / "results" / "e1_sweep"
PAIRS = ROOT / "corpus" / "e1_errata" / "pairs_g1g2.jsonl"
OUT = ROOT / "results" / "e1_analysis.json"

SEED = 20260805
N_BOOT = 10_000
OPERATING_POINTS = [0.30, 0.40, 0.60, 0.80, 0.85, 0.95]
TOKEN = re.compile(r"[a-z0-9]+")
KW = re.compile(r"\b(MUST NOT|SHALL NOT|SHOULD NOT|NOT RECOMMENDED|MUST|REQUIRED|SHALL|SHOULD|RECOMMENDED|MAY|OPTIONAL)\b")
NUM = re.compile(r"\d+(?:\.\d+)?")


def jaccard(a: str, b: str) -> float:
    ta, tb = set(TOKEN.findall(a.lower())), set(TOKEN.findall(b.lower()))
    return len(ta & tb) / len(ta | tb) if (ta or tb) else 1.0


def auroc(scores_pos: np.ndarray, scores_neg: np.ndarray) -> float:
    """P(pos < neg) — positive class (Technical) expected LOWER."""
    if len(scores_pos) == 0 or len(scores_neg) == 0:
        return float("nan")
    allv = np.concatenate([scores_pos, scores_neg])
    ranks = np.argsort(np.argsort(allv, kind="stable")).astype(float) + 1.0
    # tie-average ranks
    order = np.argsort(allv, kind="stable")
    sv = allv[order]
    i = 0
    while i < len(sv):
        j = i
        while j + 1 < len(sv) and sv[j + 1] == sv[i]:
            j += 1
        if j > i:
            ranks[order[i:j + 1]] = ranks[order[i:j + 1]].mean()
        i = j + 1
    r_pos = ranks[: len(scores_pos)].sum()
    n1, n2 = len(scores_pos), len(scores_neg)
    u = r_pos - n1 * (n1 + 1) / 2.0
    return 1.0 - (u / (n1 * n2))  # P(pos < neg)


def main() -> None:
    rows = [json.loads(l) for l in PAIRS.read_text(encoding="utf-8").splitlines()]
    meta = {r["pair_id"]: r for r in rows}
    for r in rows:
        r["jaccard"] = jaccard(r["g2_orig"], r["g2_corr"])
        kwc = Counter(KW.findall(r["g2_orig"])) != Counter(KW.findall(r["g2_corr"]))
        numc = Counter(NUM.findall(r["g2_orig"])) != Counter(NUM.findall(r["g2_corr"]))
        r["edit_class"] = "kw2119" if kwc else ("number" if numc else "other")

    configs = sorted(SWEEP.glob("*.json"))
    if not configs:
        sys.exit("no sweep results present")
    rng = np.random.default_rng(SEED)
    report = {"seed": SEED, "n_boot": N_BOOT, "configs": {}, "hypotheses": {}}
    pop = lambda r: r["status"] == "Verified" and not r["code_primary"]

    h1_rates, h2_marginals, h2_moves, h3_hits, g_means = {}, [], [], [], defaultdict(list)

    for cf in configs:
        data = json.loads(cf.read_text())
        name = data["config"]
        entry = {"family": data["family"], "granularities": {}}
        for g, scores in data["granularities"].items():
            ids = [pid for pid in scores if pid in meta and pop(meta[pid])]
            cos = np.array([scores[pid] for pid in ids])
            lab = np.array([meta[pid]["type"] == "Technical" for pid in ids])
            jac = np.array([meta[pid]["jaccard"] for pid in ids])
            docs = np.array([meta[pid]["doc_id"] for pid in ids])
            gE = {}
            gE["n_T"], gE["n_E"] = int(lab.sum()), int((~lab).sum())
            marg = auroc(cos[lab], cos[~lab])
            gE["auroc_marginal"] = round(marg, 4)
            # cluster bootstrap by doc
            udocs = np.unique(docs)
            doc_idx = {d: np.flatnonzero(docs == d) for d in udocs}
            boots = np.empty(N_BOOT)
            for b in range(N_BOOT):
                sel = rng.choice(udocs, size=len(udocs), replace=True)
                idx = np.concatenate([doc_idx[d] for d in sel])
                boots[b] = auroc(cos[idx][lab[idx]], cos[idx][~lab[idx]])
            gE["auroc_ci95"] = [round(float(np.nanpercentile(boots, 2.5)), 4),
                                round(float(np.nanpercentile(boots, 97.5)), 4)]
            # overlap-decile stratification
            deciles = np.quantile(jac, np.linspace(0, 1, 11))
            strat_aucs, weights = [], []
            for d in range(10):
                m = (jac >= deciles[d]) & (jac <= deciles[d + 1] if d == 9 else jac < deciles[d + 1])
                if lab[m].sum() and (~lab[m]).sum():
                    strat_aucs.append(auroc(cos[m][lab[m]], cos[m][~lab[m]]))
                    weights.append(m.sum())
            strat = float(np.average(strat_aucs, weights=weights)) if strat_aucs else float("nan")
            gE["auroc_stratified"] = round(strat, 4)
            gE["stratification_movement"] = round(abs(marg - strat), 4)
            # operating points
            ops = {}
            for t in OPERATING_POINTS:
                fires = cos < t  # gate flags "changed" below threshold
                tpr = float(fires[lab].mean()) if lab.sum() else float("nan")
                tnr = float((~fires[~lab]).mean()) if (~lab).sum() else float("nan")
                ops[str(t)] = {"technical_flagged": round(tpr, 4), "editorial_passed": round(tnr, 4),
                               "balanced_accuracy": round((tpr + tnr) / 2, 4),
                               "technical_above_threshold": round(float((cos[lab] >= t).mean()), 4)}
            gE["operating_points"] = ops
            gE["median_cosine_T"] = round(float(np.median(cos[lab])), 4)
            gE["median_cosine_E"] = round(float(np.median(cos[~lab])), 4)
            # edit classes (Technical only)
            cls = {}
            for c in ("kw2119", "number", "other"):
                m = lab & np.array([meta[pid]["edit_class"] == c for pid in ids])
                if m.sum():
                    cls[c] = {"n": int(m.sum()), "median_cosine": round(float(np.median(cos[m])), 4)}
            gE["edit_classes"] = cls
            entry["granularities"][g] = gE
            g_means[g].append(marg)
            if g == "g2":
                h2_marginals.append((name, marg))
                h2_moves.append((name, gE["stratification_movement"]))
                h1_rates[name] = {"ge_080": gE["operating_points"]["0.8"]["technical_above_threshold"],
                                  "ge_085": gE["operating_points"]["0.85"]["technical_above_threshold"],
                                  "ge_095": gE["operating_points"]["0.95"]["technical_above_threshold"],
                                  "median_T": gE["median_cosine_T"]}
                med = sorted(((c, v["median_cosine"]) for c, v in cls.items()), key=lambda x: -x[1])
                top2 = {c for c, _ in med[:2]}
                h3_hits.append(top2 == {"kw2119", "number"} and all(
                    cls[c]["median_cosine"] >= 0.97 for c in ("kw2119", "number") if c in cls))
        report["configs"][name] = entry

    # Hypothesis scorecard (bars from PREREGISTRATION_E1 section 3)
    report["hypotheses"]["H1"] = {
        "bar": ">=90% of Verified-Technical above cosine 0.80 at g2; median T >= 0.95",
        "per_config": h1_rates,
        "pass": bool(h1_rates and all(v["ge_080"] >= 0.90 for v in h1_rates.values())
                     and all(v["median_T"] >= 0.95 for v in h1_rates.values())),
    }
    report["hypotheses"]["H2"] = {
        "bar": "marginal AUROC in [0.45,0.65] for ALL configs at g2 AND movement < 0.05",
        "marginals": {n: round(a, 4) for n, a in h2_marginals},
        "movements": {n: m for n, m in h2_moves},
        "pass_range": bool(h2_marginals and all(0.45 <= a <= 0.65 for _, a in h2_marginals)),
        "pass_movement": bool(h2_moves and all(m < 0.05 for _, m in h2_moves)),
    }
    report["hypotheses"]["H3"] = {
        "bar": "kw2119+number are the top-2 Technical classes by median cosine, each >=0.97, in >=7/9 configs",
        "hits": int(sum(h3_hits)), "of": len(h3_hits), "pass": sum(h3_hits) >= 7,
    }
    report["hypotheses"]["H4"] = {"status": "PENDING bis corpus (E1-P6)"}
    decay = {g: round(float(np.mean(v)), 4) for g, v in g_means.items()}
    report["hypotheses"]["H5"] = {
        "bar": "mean AUROC decays monotonically g1->g2->g3, total drop >= 0.10",
        "mean_auroc_by_granularity": decay,
        "pass": bool(all(k in decay for k in ("g1", "g2", "g3"))
                     and decay["g1"] >= decay["g2"] >= decay["g3"]
                     and (decay["g1"] - decay["g3"]) >= 0.10),
    }
    OUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["hypotheses"], indent=2))
    print(f"\nconfigs analyzed: {len(report['configs'])} (of 9 expected)")


if __name__ == "__main__":
    main()
