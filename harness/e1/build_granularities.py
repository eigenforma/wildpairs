"""E1-P2: build granularities g1 (changed-sentence) and g2 (quoted-passage) for every
eligible errata pair, emit the frozen pair list and its statistics. Encoder-blind.

g2 = the orig_text/correct_text fields as filed (whitespace-normalized copies recorded).
g1 = the minimal changed sentence span: both texts are whitespace-normalized, sentence-split
on (?<=[.!?])\\s+ , aligned with difflib.SequenceMatcher; g1 is the join of changed slots on
each side (with one sentence of shared context when the changed span is empty on one side,
e.g. pure insertions). n_changed_slots is recorded per pair; pairs whose normalized texts are
identical (pure-whitespace corrections) are counted and excluded from g1 analyses only.

Output: corpus/e1_errata/pairs_g1g2.jsonl (one record per pair, stable pair_id) and
results/verification/e1_granularity_stats.json. Section-context (g3) is built separately
on the host holding RFC full text (harness/e1/locate_sections.py).
"""
import difflib
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "harness"))
from lib.filters import is_code_primary  # noqa: E402

SNAPSHOT = ROOT / "corpus" / "e1_errata" / "errata.json"
OUT_PAIRS = ROOT / "corpus" / "e1_errata" / "pairs_g1g2.jsonl"
OUT_STATS = ROOT / "results" / "verification" / "e1_granularity_stats.json"

SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def sentences(text: str):
    return [s for s in SENT_SPLIT.split(text) if s]


def g1_pair(orig: str, corr: str):
    sa, sb = sentences(orig), sentences(corr)
    ops = [o for o in difflib.SequenceMatcher(a=sa, b=sb, autojunk=False).get_opcodes() if o[0] != "equal"]
    n_slots = sum(max(i2 - i1, j2 - j1) for _, i1, i2, j1, j2 in ops)
    if not ops:
        return None, None, 0
    a_lo, a_hi = min(o[1] for o in ops), max(o[2] for o in ops)
    b_lo, b_hi = min(o[3] for o in ops), max(o[4] for o in ops)
    ga = " ".join(sa[a_lo:a_hi]) or " ".join(sa[max(0, a_lo - 1):a_hi + 1])
    gb = " ".join(sb[b_lo:b_hi]) or " ".join(sb[max(0, b_lo - 1):b_hi + 1])
    return ga, gb, n_slots


def main() -> None:
    data = json.loads(SNAPSHOT.read_bytes())
    stats = {"snapshot_entries": len(data)}
    kept, code_stratum, identical_after_norm = [], 0, 0
    strata = Counter()

    for e in data:
        status = e.get("errata_status_code")
        etype = e.get("errata_type_code")
        if status not in ("Verified", "Held for Document Update"):
            continue
        if etype not in ("Technical", "Editorial"):
            continue
        orig, corr = (e.get("orig_text") or "").strip(), (e.get("correct_text") or "").strip()
        if not orig or not corr:
            continue
        no, nc = norm(orig), norm(corr)
        code = is_code_primary(orig, corr)
        if no == nc:
            identical_after_norm += 1
            continue
        g1o, g1c, n_slots = g1_pair(no, nc)
        rec = {
            "pair_id": f"eid{e.get('errata_id')}",
            "doc_id": e.get("doc-id"),
            "status": status,
            "type": etype,
            "code_primary": code,
            "n_changed_sentence_slots": n_slots,
            "g1_orig": g1o,
            "g1_corr": g1c,
            "g2_orig": no,
            "g2_corr": nc,
            "section": e.get("section"),
        }
        if code:
            code_stratum += 1
        strata[(status, etype, "code" if code else "prose")] += 1
        kept.append(rec)

    with OUT_PAIRS.open("w", encoding="utf-8") as f:
        for r in kept:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    slots = Counter(r["n_changed_sentence_slots"] for r in kept if not r["code_primary"] and r["status"] == "Verified")
    stats.update(
        {
            "pairs_emitted": len(kept),
            "identical_after_whitespace_norm_excluded": identical_after_norm,
            "code_primary_pairs": code_stratum,
            "strata": {f"{s}|{t}|{c}": n for (s, t, c), n in sorted(strata.items())},
            "verified_prose_changed_slot_distribution": {
                "1": slots.get(1, 0),
                "2": slots.get(2, 0),
                "3plus": sum(v for k, v in slots.items() if k >= 3),
            },
            "algorithm": "whitespace-norm; sentence split (?<=[.!?])\\s+; SequenceMatcher opcodes; slots = max(a-span, b-span) summed over non-equal ops",
        }
    )
    OUT_STATS.parent.mkdir(parents=True, exist_ok=True)
    OUT_STATS.write_text(json.dumps(stats, indent=2) + "\n")
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
