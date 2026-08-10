"""Regenerate results/verification/e1_bis_stats.json to carry the per-class token-Jaccard
medians it is cited for (findings_h4 three-regime table; review F5/A8), alongside the
original mining counts. Medians computed from the frozen bis corpus under the pinned
tokenizer (prereg-e1 §2: lowercase [a-z0-9]+ runs, set Jaccard).
"""
import json, re, statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "results" / "verification" / "e1_bis_stats.json"

tok = lambda s: set(re.findall(r"[a-z0-9]+", s.lower()))
def jac(a, b):
    u = a | b
    return len(a & b) / len(u) if u else 1.0

J = {"strength_transition": [], "keyword_preserved_rewording": []}
with open(ROOT / "corpus" / "e1_errata" / "bis_pairs.jsonl", encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        if r["label"] in J:
            J[r["label"]].append(jac(tok(r["old_sentence"]), tok(r["new_sentence"])))

d = json.loads(P.read_text(encoding="utf-8"))
d["jaccard_medians_pinned_tokenizer"] = {
    k: round(statistics.median(v), 4) for k, v in J.items()
}
d["jaccard_medians_note"] = ("added 2026-08-10 (review F5/A8): per-class medians under the "
                             "prereg-e1 §2 tokenizer, recompute: scripts/regen_e1_bis_stats.py")
P.write_text(json.dumps(d, indent=1) + "\n", encoding="utf-8")
print(json.dumps(d["jaccard_medians_pinned_tokenizer"], indent=1))
