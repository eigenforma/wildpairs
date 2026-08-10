"""E1-P5 first arm: build the 300-pair errata label-noise annotation packet (amendment A5).

Stratification (recorded here, disclosed in the packet metadata):
  Technical side: 150 Verified-prose pairs, balanced 50/50/50 over the executed
    three-class partition (kw2119 / number / other) — balance over proportionality so
    per-class noise ceilings carry comparable precision.
  Editorial side: 150 Verified-prose pairs, uniform random.
  Texts: g1 (changed-sentence granularity) — like-for-like with the bis audit's
    sentence-level items. Item order shuffled; A/B presentation order randomized
    per item. Seed 20260810 (all draws).

Outputs (results/verification/):
  errata_audit_blind_packet.json   [{item, text_A, text_B}]        -> annotator seats ONLY
  errata_audit_sample_300.jsonl    full rows incl. machine labels  -> SEALED until adjudication
  errata_audit_key.json            item -> {pair_id, type, class, order} -> SEALED
The annotator protocol lives in docs/annotation_protocol_errata.md; per A5 the
annotators judge the construct blind to the IETF type.
"""
import json, random, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V = ROOT / "results" / "verification"
SEED = 20260810
rng = random.Random(SEED)

KW = ["MUST NOT", "MUST", "REQUIRED", "SHALL NOT", "SHALL", "SHOULD NOT", "SHOULD",
      "RECOMMENDED", "NOT RECOMMENDED", "MAY", "OPTIONAL"]

def kw_multiset(s):
    counts = {}
    t = s
    for k in KW:  # longest-first so MUST NOT is not double-counted as MUST
        n = len(re.findall(r"\b" + k.replace(" ", r"\s+") + r"\b", t))
        if n:
            counts[k] = n
            t = re.sub(r"\b" + k.replace(" ", r"\s+") + r"\b", " ", t)
    return counts

num_multiset = lambda s: sorted(re.findall(r"\d+(?:\.\d+)?", s))

def edit_class(orig, corr):
    if kw_multiset(orig) != kw_multiset(corr):
        return "kw2119"
    if num_multiset(orig) != num_multiset(corr):
        return "number"
    return "other"

rows = [json.loads(l) for l in
        (ROOT / "corpus" / "e1_errata" / "pairs_g1g2.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
prose = [r for r in rows if r["status"] == "Verified" and not r["code_primary"]
         and r["g1_orig"].strip() and r["g1_corr"].strip()]
tech = [r for r in prose if r["type"] == "Technical"]
edit = [r for r in prose if r["type"] == "Editorial"]
print(f"Verified-prose pool: {len(tech)} T / {len(edit)} E")

by_class = {"kw2119": [], "number": [], "other": []}
for r in tech:
    by_class[edit_class(r["g1_orig"], r["g1_corr"])].append(r)
print("T class pool:", {k: len(v) for k, v in by_class.items()})

sample = []
for cls in ("kw2119", "number", "other"):
    pool = sorted(by_class[cls], key=lambda r: r["pair_id"])
    take = rng.sample(pool, min(50, len(pool)))
    for r in take:
        sample.append((r, cls))
epool = sorted(edit, key=lambda r: r["pair_id"])
for r in rng.sample(epool, 150):
    sample.append((r, "editorial-na"))

rng.shuffle(sample)
packet, key, full = [], {}, []
for i, (r, cls) in enumerate(sample):
    flip = rng.random() < 0.5
    a, b = (r["g1_corr"], r["g1_orig"]) if flip else (r["g1_orig"], r["g1_corr"])
    packet.append({"item": i, "text_A": a, "text_B": b})
    key[i] = {"pair_id": r["pair_id"], "doc_id": r["doc_id"], "type": r["type"],
              "edit_class": cls, "A_is": "corr" if flip else "orig"}
    full.append({"item": i, **{k: r[k] for k in ("pair_id", "doc_id", "type", "g1_orig", "g1_corr")},
                 "edit_class": cls})

(V / "errata_audit_blind_packet.json").write_text(json.dumps(packet, indent=1), encoding="utf-8")
(V / "errata_audit_key.json").write_text(json.dumps(
    {"seed": SEED, "stratification": "T: 50/50/50 kw2119/number/other; E: 150 uniform; g1 texts",
     "items": key}, indent=1), encoding="utf-8")
with open(V / "errata_audit_sample_300.jsonl", "w", encoding="utf-8") as f:
    for row in full:
        f.write(json.dumps(row) + "\n")
n_t = sum(1 for v in key.values() if v["type"] == "Technical")
print(f"packet: {len(packet)} items ({n_t} T / {len(packet)-n_t} E), seed {SEED}")
