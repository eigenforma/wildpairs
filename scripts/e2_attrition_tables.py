"""Pre-tag table: per-bin anchor attrition under the pinned drop rule (PREREGISTRATION_E2 §2).

Rule, pinned 2026-08-08: an anchor drops from bin L when
    max(ws_tokens(payload_orig), ws_tokens(payload_para), ws_tokens(payload_affirm)) > W(L)/2,
    W(L) = ceil(L / 1.3)   (the bin's whitespace construction budget).
Eligibility is monotone in L, so the constant cohort = anchors eligible at the smallest
fitted bin. Encoder-blind and lexical; safe before the tag. Output feeds §6 at tag time.

Recompute: python scripts/e2_attrition_tables.py
Frozen:    results/verification/e2_attrition_tables.json
"""
import json, math, statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BINS = [64, 96, 128, 256, 512, 1024, 2048, 4096]

anchors = [json.loads(l) for l in
           (ROOT / "corpus" / "e2_dilution" / "anchors_frozen.jsonl").read_text(encoding="utf-8").splitlines()
           if l.strip()]
assert len(anchors) == 959

ws = lambda s: len(s.split())
def stats(vals):
    v = sorted(vals)
    return {"n": len(v), "median": v[len(v)//2] if v else None,
            "p90": v[int(len(v)*0.9)] if v else None, "max": v[-1] if v else None}

orig = [ws(a["payload_orig"]) for a in anchors]
maxm = [max(ws(a["payload_orig"]), ws(a["payload_para"]), ws(a["payload_affirm"])) for a in anchors]
scope_present = [a for a in anchors if a.get("payload_scope")]
maxm_scope = {a["anchor_id"]: max(ws(a["payload_orig"]), ws(a["payload_scope"])) for a in scope_present}

table = {}
for L in BINS:
    cut = math.ceil(L / 1.3) / 2
    dropped = [m for m in maxm if m > cut]
    table[str(L)] = {
        "ws_budget_W": math.ceil(L / 1.3), "cut_max_member_gt": cut,
        "eligible": len(maxm) - len(dropped), "dropped": len(dropped),
        "dropped_frac": round(len(dropped) / len(maxm), 4),
        "dropped_payload_stats": stats(dropped) if dropped else None,
        "scope_eligible": sum(1 for a in scope_present if maxm_scope[a["anchor_id"]] <= cut),
    }

cohort64 = table["64"]["eligible"]     # eligibility monotone => cohort over all bins = eligible@64
cohort96 = table["96"]["eligible"]
out = {
    "computed": "2026-08-10, pre-tag (encoder-blind, lexical)",
    "rule": "drop from bin L if max ws-tokens over (orig, para, affirm) > ceil(L/1.3)/2; anchor-level",
    "anchor_payload_stats": {"orig": stats(orig), "max_member": stats(maxm)},
    "per_bin": table,
    "constant_cohort_all_bins_incl_64": cohort64,
    "constant_cohort_96_floor": cohort96,
    "floor_rule_verdict": ("cohort@64 >= 400: L=64 stays the constant-cohort fit floor"
                           if cohort64 >= 400 else
                           f"cohort@64 = {cohort64} < 400: per PREREGISTRATION_E2 §2 the L=96 bin "
                           f"becomes the constant-cohort fit floor (cohort@96 = {cohort96}); disclosed"),
    "scope_control_present": len(scope_present),
}
dest = ROOT / "results" / "verification" / "e2_attrition_tables.json"
dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
print(json.dumps(out, indent=2))
