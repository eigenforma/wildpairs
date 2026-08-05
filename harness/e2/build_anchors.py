"""E2 anchor extraction: from the frozen CondaQA splits, build the frozen anchor-set list
for the dilution titration. Encoder-blind; runs before prereg-e2 freezes and its outputs
are pinned by that tag.

An anchor set = a passage whose PARAPHRASE (edit 1) and AFFIRMATIVE (edit 3) edits are both
recoverable as single-sentence substitutions vs the original (edit 0), under the same
sentence-diff algorithm as scripts/verify_condaqa.py (estimate and pipeline agree by
construction). SCOPE (edit 2) is carried when it is also single-sentence (high-overlap flip
control). Payload-level token-Jaccard is computed per edit type — the imported-confounder
measurement the E2 prereg discloses (CondaQA affirmative edits are high-overlap by nature,
paraphrase edits lower; Paper A section 3's coupling arrives with the dataset).

Output: corpus/e2_dilution/anchors_frozen.jsonl, results/verification/e2_anchor_stats.json.
"""
import difflib
import json
import re
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DIR = ROOT / "corpus" / "e2_dilution"
OUT_ANCHORS = DIR / "anchors_frozen.jsonl"
OUT_STATS = ROOT / "results" / "verification" / "e2_anchor_stats.json"

SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
TOKEN = re.compile(r"[a-z0-9]+")


def sentences(text: str):
    return [s.strip() for s in SENT_SPLIT.split(text.strip()) if s.strip()]


def jaccard(a: str, b: str) -> float:
    ta, tb = set(TOKEN.findall(a.lower())), set(TOKEN.findall(b.lower()))
    return len(ta & tb) / len(ta | tb) if (ta or tb) else 1.0


def single_sentence_sub(orig: str, edited: str):
    """Return (orig_sentence, edited_sentence, index) when the edit is exactly one changed
    slot; else None."""
    sa, sb = sentences(orig), sentences(edited)
    ops = [o for o in difflib.SequenceMatcher(a=sa, b=sb, autojunk=False).get_opcodes() if o[0] != "equal"]
    slots = sum(max(i2 - i1, j2 - j1) for _, i1, i2, j1, j2 in ops)
    if slots != 1 or len(ops) != 1:
        return None
    _, i1, i2, j1, j2 = ops[0]
    if i2 - i1 != 1 or j2 - j1 != 1:
        return None  # insert/delete, not substitution
    return sa[i1], sb[j1], i1


def main() -> None:
    variants = {}
    for split in ("train", "dev", "test"):
        for line in (DIR / f"condaqa_{split}.json").read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            variants[(split, r["PassageID"], str(r["PassageEditID"]))] = r["sentence1"]

    by_passage = defaultdict(dict)
    for (split, pid, eid), text in variants.items():
        by_passage[(split, pid)][eid] = text

    anchors, jac = [], defaultdict(list)
    n_candidates = 0
    for (split, pid), ed in sorted(by_passage.items(), key=lambda kv: (kv[0][0], str(kv[0][1]))):
        if not all(k in ed for k in ("0", "1", "3")):
            continue
        n_candidates += 1
        para = single_sentence_sub(ed["0"], ed["1"])
        affirm = single_sentence_sub(ed["0"], ed["3"])
        if not (para and affirm):
            continue
        scope = single_sentence_sub(ed["0"], ed["2"]) if "2" in ed else None
        rec = {
            "anchor_id": f"{split}-{pid}",
            "split": split,
            "passage": ed["0"],
            "payload_orig": para[0],
            "payload_para": para[1],
            "payload_affirm": affirm[1],
            "para_sent_idx": para[2],
            "affirm_sent_idx": affirm[2],
            "same_sentence_edited": para[2] == affirm[2],
            "j_para": round(jaccard(para[0], para[1]), 4),
            "j_affirm": round(jaccard(affirm[0], affirm[1]), 4),
        }
        if scope:
            rec["payload_scope"] = scope[1]
            rec["j_scope"] = round(jaccard(scope[0], scope[1]), 4)
        jac["para"].append(rec["j_para"])
        jac["affirm"].append(rec["j_affirm"])
        if scope:
            jac["scope"].append(rec["j_scope"])
        anchors.append(rec)

    with OUT_ANCHORS.open("w", encoding="utf-8") as f:
        for a in anchors:
            f.write(json.dumps(a, ensure_ascii=False) + "\n")

    same_idx = sum(a["same_sentence_edited"] for a in anchors)
    stats = {
        "candidates_with_0_1_3": n_candidates,
        "anchors_frozen": len(anchors),
        "with_scope_control": sum("payload_scope" in a for a in anchors),
        "same_sentence_edited_rate": round(same_idx / len(anchors), 4) if anchors else None,
        "per_split": {s: sum(a["split"] == s for a in anchors) for s in ("train", "dev", "test")},
        "payload_jaccard": {
            k: {"n": len(v), "median": round(statistics.median(v), 4), "mean": round(statistics.mean(v), 4)}
            for k, v in jac.items()
        },
        "imported_confounder_gap_median_affirm_minus_para": round(
            statistics.median(jac["affirm"]) - statistics.median(jac["para"]), 4) if jac["affirm"] and jac["para"] else None,
        "algorithm": "single changed slot via SequenceMatcher over (?<=[.!?])\\s+ sentences; substitution-only (1:1 slot)",
    }
    OUT_STATS.write_text(json.dumps(stats, indent=2) + "\n")
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
