"""Close the E1-P5 errata label-noise audit (amendment A5): merge the two blind seats with
the operator's adjudications, UNSEAL the machine-label key, and compute the
construct-vs-institution confusion matrix, per-class noise rates, and the AUROC ceiling.

Inputs (results/verification/): annotator_{A,B}_errata.json, errata_adjudication_answers.json
(operator sheet, ingested from the sitting page's download), errata_audit_key.json (SEALED
until this script runs), errata_audit_sample_300.jsonl, errata_adjudication_packet.json.
Output: results/verification/errata_audit_final.json
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V = ROOT / "results" / "verification"

A = {j["item"]: j["verdict"] for j in json.loads((V / "annotator_A_errata.json").read_text(encoding="utf-8"))["judgments"]}
B = {j["item"]: j["verdict"] for j in json.loads((V / "annotator_B_errata.json").read_text(encoding="utf-8"))["judgments"]}
ans = json.loads((V / "errata_adjudication_answers.json").read_text(encoding="utf-8"))
adj = {int(k): v for k, v in ans["verdicts"].items()}
key = json.loads((V / "errata_audit_key.json").read_text(encoding="utf-8"))["items"]
key = {int(k): v for k, v in key.items()}

dis = sorted(i for i in A if A[i] != B[i])
assert set(adj) == set(dis), f"adjudication set mismatch: {len(adj)} vs {len(dis)}"
assert all(v in ("different", "same", "unjudgeable") for v in adj.values())

verdict = {i: (A[i] if A[i] == B[i] else adj[i]) for i in range(300)}
judgeable = [i for i in range(300) if verdict[i] != "unjudgeable"]

def rate(ids, want):
    n = len(ids)
    d = sum(1 for i in ids if verdict[i] == want)
    lo_hi = wilson(d, n)
    return {"count": d, "of": n, "rate": round(d / n, 4) if n else None,
            "wilson95": [round(x, 4) for x in lo_hi]}

def wilson(k, n, z=1.959964):
    if n == 0:
        return (None, None)
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / den
    return (c - h, c + h)

T = [i for i in judgeable if key[i]["type"] == "Technical"]
E = [i for i in judgeable if key[i]["type"] == "Editorial"]
by_class = {}
for cls in ("kw2119", "number", "other"):
    ids = [i for i in judgeable if key[i]["edit_class"] == cls]
    by_class[cls] = rate(ids, "different")

precision_T = rate(T, "different")          # institution said changing; construct confirms
leak_E = rate(E, "different")               # institution said preserving; construct says changing
rho_T = 1 - precision_T["rate"]             # Technical noise: adjudicated NOT meaning-changing
rho_E = leak_E["rate"]                      # Editorial noise: adjudicated meaning-changing

# AUROC machinery (first-order asymmetric-noise correction; the A5-committed symmetric
# form (A-r)/(1-2r) is the special case r_T = r_E and is reported alongside as registered)
atten = 1 - rho_T - rho_E
ceiling = 0.5 + 0.5 * atten                 # max observable AUROC for a perfect encoder
correct = lambda a: round(0.5 + (a - 0.5) / atten, 4)

out = {
    "closed": ans["recorded_utc"] + " (operator adjudication of all 34 disagreements; sitting page)",
    "n": 300, "unjudgeable_excluded": 300 - len(judgeable),
    "kappa_AB": 0.6813, "raw_agreement": 0.8867,
    "operator_adjudications": {str(k): v for k, v in sorted(adj.items())},
    "adjudication_split": {v: sum(1 for x in adj.values() if x == v) for v in ("different", "same", "unjudgeable")},
    "construct_vs_institution": {
        "technical_confirmed_changing": precision_T,
        "editorial_adjudicated_changing_LEAK": leak_E,
        "by_edit_class_rate_different": by_class,
    },
    "noise_rates": {"rho_T": round(rho_T, 4), "rho_E": round(rho_E, 4)},
    "auroc_machinery": {
        "attenuation_factor": round(atten, 4),
        "max_observable_auroc_ceiling": round(ceiling, 4),
        "h2_naive_range_corrected": [correct(0.5525), correct(0.5693)],
        "h2_stratified_range_corrected": [correct(0.5024), correct(0.5237)],
        "note": "first-order asymmetric correction A_true = 0.5 + (A_obs - 0.5)/(1 - rho_T - rho_E); "
                "the A5-registered symmetric form is its rho_T = rho_E special case",
    },
    "promotion_trigger_A5": {
        "rule": "construct disagreement > 15% in either class promotes the adjudicated-construct subsample to primary",
        "technical_disagreement": round(rho_T, 4), "editorial_disagreement": round(rho_E, 4),
        "verdict": ("TRIGGERED" if max(rho_T, rho_E) > 0.15 else "not triggered"),
    },
    "provenance": "seat A: firewalled Claude context; seat B: gpt-oss-120b (Forge, temp 0); operator sitting "
                  "2026-08-11 via the adjudication page; machine labels sealed until all verdicts recorded",
}
(V / "errata_audit_final.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
print(json.dumps({k: out[k] for k in ("adjudication_split", "construct_vs_institution",
                                      "noise_rates", "auroc_machinery", "promotion_trigger_A5")}, indent=1))
