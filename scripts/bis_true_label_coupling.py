"""A8: exact true-label bis coupling from the audit's full annotator vectors.

Replaces the review's admissible-bounds computation (+0.080..+0.259) with the exact
corrected medians findings_h4 cites. Validates everything against the frozen audit
artifacts before computing; any checksum failure aborts.

Inputs (all frozen in this repo):
  results/verification/annotator_A_judgments.json   (rescued 2026-08-10)
  results/verification/annotator_B_judgments.json   (rescued 2026-08-10)
  results/verification/bis_adjudication_packet.json (35 disagreements, A/B votes)
  results/verification/bis_audit_final.json         (operator adjudications, aggregates)
  results/verification/bis_audit_sample_200.jsonl   (item i = line i; machine labels)
Output: results/verification/bis_true_label_coupling.json
"""
import json, re, statistics, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V = ROOT / "results" / "verification"

tok = lambda s: set(re.findall(r"[a-z0-9]+", s.lower()))          # pinned tokenizer (prereg-e1 §2)
def jac(a, b):
    u = a | b
    return len(a & b) / len(u) if u else 1.0

A = json.loads((V / "annotator_A_judgments.json").read_text(encoding="utf-8"))["judgments"]
B = json.loads((V / "annotator_B_judgments.json").read_text(encoding="utf-8"))["judgments"]
packet = json.loads((V / "bis_adjudication_packet.json").read_text(encoding="utf-8"))
blind = json.loads((V / "bis_audit_blind_packet.json").read_text(encoding="utf-8"))
final = json.loads((V / "bis_audit_final.json").read_text(encoding="utf-8"))
raw_sample = [json.loads(l) for l in (V / "bis_audit_sample_200.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]

assert len(A) == len(B) == len(raw_sample) == len(blind) == 200
Av = {j["item"]: j["verdict"] for j in A}
Bv = {j["item"]: j["verdict"] for j in B}

# --- join: vector item numbers are BLIND-PACKET items (shuffled, randomized A/B order);
#     map each blind item back to its sample row by exact unordered text match
norm = lambda s: re.sub(r"\s+", " ", s.strip())
by_texts = {}
for r in raw_sample:
    by_texts.setdefault(frozenset((norm(r["old_sentence"]), norm(r["new_sentence"]))), []).append(r)
dup_groups = {k: v for k, v in by_texts.items() if len(v) > 1}
for k, rows in dup_groups.items():
    assert len({r["label"] for r in rows}) == 1, "duplicate texts with conflicting machine labels"
sample = {}
for it in blind:
    i = int(it["item"])
    key = frozenset((norm(it["text_A"]), norm(it["text_B"])))
    assert key in by_texts, f"blind item {i} not found in sample"
    sample[i] = by_texts[key][0]   # duplicates share label and Jaccard by construction
assert len(sample) == 200

# --- checksum 1: disagreement set == adjudication packet, with matching votes and texts
dis = sorted(i for i in Av if Av[i] != Bv[i])
pk = {int(it["item"]): it for it in packet["items"]}
assert len(dis) == len(pk) == 35, (len(dis), len(pk))
for i in dis:
    it = pk[i]
    assert Av[i] == it["annotator_A"] and Bv[i] == it["annotator_B"], f"vote mismatch item {i}"
    assert norm(it["text_A"]).startswith(norm(blind[i]["text_A"])[:40]), f"packet/blind text mismatch item {i}"

# --- checksum 2: Cohen kappa reproduces the packet's
cats = ["different", "same", "unjudgeable"]
n = 200
po = sum(1 for i in Av if Av[i] == Bv[i]) / n
pe = sum((sum(1 for i in Av if Av[i] == c) / n) * (sum(1 for i in Bv if Bv[i] == c) / n) for c in cats)
kappa = (po - pe) / (1 - pe)
assert abs(kappa - packet["kappa_AB"]) < 5e-4, (kappa, packet["kappa_AB"])

# --- final verdict per item: agreement, else operator adjudication
adj = {int(k): v for k, v in final["operator_adjudications"].items()}
assert set(adj) == set(dis), "adjudication set != disagreement set"
verdict = {i: (Av[i] if Av[i] == Bv[i] else adj[i]) for i in range(200)}

# --- checksum 3: reproduce the frozen aggregates
mach = {i: sample[i]["label"] for i in range(200)}
judgeable = [i for i in range(200) if verdict[i] != "unjudgeable"]
assert 200 - len(judgeable) == final["unjudgeable_excluded"]
prec_n = sum(1 for i in judgeable if mach[i] == "strength_transition")
prec_d = sum(1 for i in judgeable if mach[i] == "strength_transition" and verdict[i] == "different")
leak_n = sum(1 for i in judgeable if mach[i] == "keyword_preserved_rewording")
leak_d = sum(1 for i in judgeable if mach[i] == "keyword_preserved_rewording" and verdict[i] == "different")
assert prec_d == final["label_precision_transitions"]["different"] and prec_n == final["label_precision_transitions"]["of"]
assert leak_d == final["negative_class_leak_rewordings"]["different"] and leak_n == final["negative_class_leak_rewordings"]["of"]

# --- the computation: Jaccard per item under the pinned tokenizer, medians by machine and true class
J = {i: jac(tok(sample[i]["old_sentence"]), tok(sample[i]["new_sentence"])) for i in range(200)}
def med(ids):
    return round(statistics.median(J[i] for i in ids), 4) if ids else None

m_trans = [i for i in range(200) if mach[i] == "strength_transition"]
m_rew = [i for i in range(200) if mach[i] == "keyword_preserved_rewording"]
t_chg = [i for i in judgeable if verdict[i] == "different"]
t_prs = [i for i in judgeable if verdict[i] == "same"]

out = {
    "computed": "2026-08-10, from rescued annotator vectors (A8)",
    "checksums": {"kappa_AB": round(kappa, 4), "disagreements": len(dis),
                  "precision_transitions": f"{prec_d}/{prec_n}", "leak_rewordings": f"{leak_d}/{leak_n}"},
    "machine_label_medians": {"strength_transition": med(m_trans), "keyword_preserved_rewording": med(m_rew),
                              "n": [len(m_trans), len(m_rew)]},
    "true_label_medians": {"meaning_changing": med(t_chg), "meaning_preserving": med(t_prs),
                           "n": [len(t_chg), len(t_prs)]},
    "true_label_gap_preserving_minus_changing": round(med(t_prs) - med(t_chg), 4),
    "orientation": "aligned" if med(t_prs) > med(t_chg) else "NOT aligned",
    "review_bounds_check": "exact value must lie in [+0.080, +0.259] from the 2026-08-08 admissible-bounds computation",
    "join_note": f"{len(dup_groups)} duplicate text-pair groups in the 200-sample (identical texts => identical label+Jaccard; join unaffected)",
}
(V / "bis_true_label_coupling.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
print(json.dumps(out, indent=2))
