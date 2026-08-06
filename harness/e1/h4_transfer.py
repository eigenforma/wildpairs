"""E1-P7 / H4: do errata-fitted calibrations survive the author change to bis revisions?

Fit side (in-sample): Verified-prose errata pairs at g2, cosines from the frozen sweep.
Fitted objects per configuration, exactly the prereg's repair candidates:
  (a) optimal single threshold tau (balanced accuracy, Technical flagged when cos < tau);
  (b) logistic gate on (cosine, token-Jaccard) — seeded deterministic gradient descent.
Frozen evaluation (held-out): machine-labeled bis pairs (strength_transition = positive,
keyword_preserved_rewording = negative), embedded by the same pinned registry, cached
resume-safe under results/e1_sweep_bis/. H4 bar (prereg section 3): each fitted object
drops >= 0.10 balanced accuracy or AUROC from errata to bis.

Label-noise status is reported, not hidden: bis labels are machine-assigned pending the
200-pair two-annotator audit (sample emitted to results/verification/bis_audit_sample_200.jsonl,
seed 20260805). The human-verified >=100-positives gate remains open until that audit.
"""
import json
import os
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
REGISTRY_DIR = Path(os.environ.get("PAPER_A_REGISTRY", "c:/Users/poeti/Falsifyer/experiments/factorial_pilot"))
sys.path.insert(0, str(REGISTRY_DIR))

SWEEP = ROOT / "results" / "e1_sweep"
BIS_SWEEP = ROOT / "results" / "e1_sweep_bis"
PAIRS = ROOT / "corpus" / "e1_errata" / "pairs_g1g2.jsonl"
BIS = ROOT / "corpus" / "e1_errata" / "bis_pairs.jsonl"
OUT = ROOT / "results" / "e1_h4_transfer.json"
AUDIT = ROOT / "results" / "verification" / "bis_audit_sample_200.jsonl"

TOKEN = re.compile(r"[a-z0-9]+")
SEED = 20260805


def jaccard(a: str, b: str) -> float:
    ta, tb = set(TOKEN.findall(a.lower())), set(TOKEN.findall(b.lower()))
    return len(ta & tb) / len(ta | tb) if (ta or tb) else 1.0


def auroc(pos, neg):
    allv = np.concatenate([pos, neg])
    order = np.argsort(allv, kind="stable")
    ranks = np.empty(len(allv))
    ranks[order] = np.arange(1, len(allv) + 1)
    sv = allv[order]
    i = 0
    while i < len(sv):
        j = i
        while j + 1 < len(sv) and sv[j + 1] == sv[i]:
            j += 1
        if j > i:
            ranks[order[i:j + 1]] = ranks[order[i:j + 1]].mean()
        i = j + 1
    u = ranks[: len(pos)].sum() - len(pos) * (len(pos) + 1) / 2
    return 1.0 - u / (len(pos) * len(neg))  # P(pos < neg): meaning-change expected LOWER cosine


def bal_acc(cos, lab, tau):
    flag = cos < tau
    tpr = flag[lab].mean() if lab.sum() else np.nan
    tnr = (~flag[~lab]).mean() if (~lab).sum() else np.nan
    return (tpr + tnr) / 2


def fit_threshold(cos, lab):
    taus = np.unique(np.round(cos, 4))
    scores = [bal_acc(cos, lab, t) for t in taus]
    return float(taus[int(np.argmax(scores))]), float(np.max(scores))


def fit_logistic(X, y, iters=5000, lr=0.5):
    rng = np.random.default_rng(SEED)
    mu, sd = X.mean(0), X.std(0) + 1e-9
    Xs = (X - mu) / sd
    w = rng.normal(0, 0.01, X.shape[1])
    b = 0.0
    for _ in range(iters):
        p = 1 / (1 + np.exp(-(Xs @ w + b)))
        g = p - y
        w -= lr * (Xs.T @ g / len(y) + 1e-4 * w)
        b -= lr * g.mean()
    return {"w": w.tolist(), "b": float(b), "mu": mu.tolist(), "sd": sd.tolist()}


def logistic_scores(model, X):
    Xs = (X - np.array(model["mu"])) / np.array(model["sd"])
    return 1 / (1 + np.exp(-(Xs @ np.array(model["w"]) + model["b"])))


def main() -> None:
    meta = {json.loads(l)["pair_id"]: json.loads(l) for l in PAIRS.read_text(encoding="utf-8").splitlines()}
    err_pop = {pid: r for pid, r in meta.items() if r["status"] == "Verified" and not r["code_primary"]}
    bis_rows = [json.loads(l) for l in BIS.read_text(encoding="utf-8").splitlines()]
    b_lab = np.array([r["label"] == "strength_transition" for r in bis_rows])
    b_jac = np.array([jaccard(r["old_sentence"], r["new_sentence"]) for r in bis_rows])
    b_pairs = [(r["old_sentence"], r["new_sentence"]) for r in bis_rows]

    # audit sample for the two-annotator arm (stratified half/half, seeded)
    rng = np.random.default_rng(SEED)
    pos_i = np.flatnonzero(b_lab); neg_i = np.flatnonzero(~b_lab)
    take = lambda idx, n: rng.choice(idx, size=min(n, len(idx)), replace=False)
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT.open("w", encoding="utf-8") as f:
        for i in sorted(np.concatenate([take(pos_i, 100), take(neg_i, 100)])):
            f.write(json.dumps(bis_rows[int(i)], ensure_ascii=False) + "\n")

    from encoders import REGISTRY  # noqa: E402
    BIS_SWEEP.mkdir(parents=True, exist_ok=True)
    report = {"seed": SEED, "n_bis": len(bis_rows), "n_bis_positive": int(b_lab.sum()),
              "bis_label_status": "machine-labeled; 200-pair two-annotator audit pending", "configs": {}}
    only = [s.strip().lower() for s in os.environ.get("SWEEP_ONLY", "").split(",") if s.strip()]

    for enc in REGISTRY:
        if only and not any(s in enc.name.lower() for s in only):
            continue
        slug = "".join(c if c.isalnum() or c in "-._" else "_" for c in enc.name)[:80]
        sweep_path = SWEEP / (slug + ".json")
        if not sweep_path.exists():
            continue
        ok, why = enc.available()
        if not ok:
            report["configs"][enc.name] = {"absent": why}
            continue
        cache = BIS_SWEEP / (slug + ".json")
        if cache.exists():
            b_cos = np.array(json.load(cache.open())["cos"])
        else:
            b_cos = np.array(enc.cosines(b_pairs))
            json.dump({"cos": b_cos.tolist()}, cache.open("w"))
        scores = json.loads(sweep_path.read_text())["granularities"]["g2"]
        ids = [pid for pid in scores if pid in err_pop]
        e_cos = np.array([scores[pid] for pid in ids])
        e_lab = np.array([err_pop[pid]["type"] == "Technical" for pid in ids])
        e_jac = np.array([jaccard(err_pop[pid]["g2_orig"], err_pop[pid]["g2_corr"]) for pid in ids])

        tau, ba_fit = fit_threshold(e_cos, e_lab)
        ba_bis = float(bal_acc(b_cos, b_lab, tau))
        lg = fit_logistic(np.column_stack([e_cos, e_jac]), e_lab.astype(float))
        e_s = logistic_scores(lg, np.column_stack([e_cos, e_jac]))
        b_s = logistic_scores(lg, np.column_stack([b_cos, b_jac]))
        # logistic scores: higher = Technical; AUROC directly (positive expected HIGHER score)
        lg_auc_fit = 1.0 - auroc(e_s[e_lab], e_s[~e_lab])
        lg_auc_bis = 1.0 - auroc(b_s[b_lab], b_s[~b_lab])
        report["configs"][enc.name] = {
            "threshold": {"tau": tau, "bal_acc_errata": round(ba_fit, 4), "bal_acc_bis": round(ba_bis, 4),
                          "drop": round(ba_fit - ba_bis, 4)},
            "logistic_cos_jac": {"auroc_errata": round(float(lg_auc_fit), 4), "auroc_bis": round(float(lg_auc_bis), 4),
                                 "drop": round(float(lg_auc_fit - lg_auc_bis), 4)},
            "raw_auroc_bis_cosine_only": round(float(auroc(b_cos[b_lab], b_cos[~b_lab])), 4),
        }
        print(f"{enc.name[:60]:60s} tau={tau:.3f} ba {ba_fit:.3f}->{ba_bis:.3f} lg {lg_auc_fit:.3f}->{lg_auc_bis:.3f}", flush=True)

    drops = [c["threshold"]["drop"] for c in report["configs"].values() if "threshold" in c] + \
            [c["logistic_cos_jac"]["drop"] for c in report["configs"].values() if "logistic_cos_jac" in c]
    report["H4"] = {"bar": "each fitted object drops >= 0.10 from errata to bis",
                    "min_drop": round(min(drops), 4) if drops else None,
                    "median_drop": round(float(np.median(drops)), 4) if drops else None,
                    "all_objects_drop_ge_0.10": bool(drops and all(d >= 0.10 for d in drops))}
    OUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["H4"], indent=2))


if __name__ == "__main__":
    main()
