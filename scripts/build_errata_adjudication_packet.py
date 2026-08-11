"""E1-P5 errata arm: compute kappa(A,B) over the 300 blind items and build the operator
adjudication packet for every disagreement (bis-audit pattern; machine labels stay sealed —
the packet carries texts and the two votes only, never the key).

Inputs:  results/verification/annotator_{A,B}_errata.json, errata_audit_blind_packet.json
Output:  results/verification/errata_adjudication_packet.json
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V = ROOT / "results" / "verification"

A = {j["item"]: j["verdict"] for j in json.loads((V / "annotator_A_errata.json").read_text(encoding="utf-8"))["judgments"]}
B = {j["item"]: j["verdict"] for j in json.loads((V / "annotator_B_errata.json").read_text(encoding="utf-8"))["judgments"]}
blind = {it["item"]: it for it in json.loads((V / "errata_audit_blind_packet.json").read_text(encoding="utf-8"))}
assert len(A) == len(B) == len(blind) == 300

cats = ["different", "same", "unjudgeable"]
n = 300
po = sum(1 for i in A if A[i] == B[i]) / n
pe = sum((sum(1 for i in A if A[i] == c) / n) * (sum(1 for i in B if B[i] == c) / n) for c in cats)
kappa = (po - pe) / (1 - pe)

dis = sorted(i for i in A if A[i] != B[i])
packet = {
    "instructions": ("Operator adjudication, errata label-noise arm (amendment A5). For each item "
                     "below the two blind annotators disagreed. Judge per the protocol in "
                     "docs/annotation_protocol_errata.md — from the two texts alone; the machine "
                     "labels remain sealed until every verdict is recorded."),
    "n": n, "kappa_AB": round(kappa, 4), "agreement_raw": round(po, 4),
    "n_disagreements": len(dis),
    "items": [{"item": i, "text_A": blind[i]["text_A"], "text_B": blind[i]["text_B"],
               "annotator_A": A[i], "annotator_B": B[i]} for i in dis],
}
(V / "errata_adjudication_packet.json").write_text(json.dumps(packet, indent=1), encoding="utf-8")
from collections import Counter
print(f"kappa(A,B) = {kappa:.4f}   raw agreement = {po:.4f}   disagreements = {len(dis)}")
print("A:", dict(Counter(A.values())), " B:", dict(Counter(B.values())))
