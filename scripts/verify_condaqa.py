"""E2-P0 snapshot verification for CondaQA: recompute row/passage/edit counts against the
independent second source (workflow verifier, 2026-08-05), and measure the yield-critical
fact the feasibility check flagged as unknown: how many edited passages differ from their
original in EXACTLY ONE sentence (the anchor-recovery rate for the titration design).

Sentence-diff algorithm (named, an estimate not a truth): passages are split on the regex
(?<=[.!?])\\s+ ; the two sentence lists are aligned with difflib.SequenceMatcher; a changed
sentence-slot is any replace/insert/delete opcode span, counted as max(len(a-span), len(b-span)).
Wikipedia abbreviations make this a slight over-splitter; the rate is therefore a floor-ish
estimate and the pre-registered E2 pipeline will use the same algorithm, so the estimate and
the pipeline agree by construction. Encoder-blind: lexical only.
"""
import difflib
import json
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIR = ROOT / "corpus" / "e2_dilution"
OUT = ROOT / "results" / "verification" / "e2_condaqa_verification.json"

SECOND_SOURCE = {
    "total_rows": 14182,
    "unique_passages_total": 1289,
    "unique_passages_train": 474,
    "unique_passages_dev": 115,
    "unique_passages_test": 700,
}

SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def sentences(text: str):
    return [s.strip() for s in SENT_SPLIT.split(text.strip()) if s.strip()]


def changed_slots(a: str, b: str) -> int:
    sa, sb = sentences(a), sentences(b)
    n = 0
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=sa, b=sb, autojunk=False).get_opcodes():
        if op != "equal":
            n += max(i2 - i1, j2 - j1)
    return n


def main() -> None:
    result = {}
    rows_per_split = {}
    passages_per_split = {}
    # passage text per (split-agnostic) key: (PassageID, PassageEditID) -> text
    variant_text = {}
    edit_ids = Counter()
    payload_words = []

    for split in ["train", "dev", "test"]:
        path = DIR / f"condaqa_{split}.json"
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        rows_per_split[split] = len(rows)
        pids = set()
        for r in rows:
            pid, eid = r["PassageID"], str(r["PassageEditID"])
            pids.add(pid)
            edit_ids[eid] += 1
            key = (split, pid, eid)
            if key not in variant_text:
                variant_text[key] = r["sentence1"]
                if eid == "0" and r.get("original sentence"):
                    payload_words.append(len(r["original sentence"].split()))
        passages_per_split[split] = pids

    result["rows_per_split"] = rows_per_split
    result["total_rows"] = sum(rows_per_split.values())
    result["unique_passages_train"] = len(passages_per_split["train"])
    result["unique_passages_dev"] = len(passages_per_split["dev"])
    result["unique_passages_test"] = len(passages_per_split["test"])
    overlap = (passages_per_split["train"] & passages_per_split["test"]) | (
        passages_per_split["train"] & passages_per_split["dev"]
    ) | (passages_per_split["dev"] & passages_per_split["test"])
    result["passage_id_overlap_across_splits"] = len(overlap)
    result["unique_passages_total"] = (
        len(passages_per_split["train"] | passages_per_split["dev"] | passages_per_split["test"])
        if overlap
        else sum(len(v) for v in passages_per_split.values())
    )
    result["rows_per_edit_id"] = dict(sorted(edit_ids.items()))

    # Yield measurement: per (split, PassageID), original (edit 0) vs each edit 1/2/3.
    per_edit_changed = defaultdict(Counter)  # edit id -> Counter(changed sentence slots)
    by_passage = defaultdict(dict)
    for (split, pid, eid), text in variant_text.items():
        by_passage[(split, pid)][eid] = text
    pairs_total = 0
    for (split, pid), edits in by_passage.items():
        if "0" not in edits:
            continue
        for eid in ("1", "2", "3"):
            if eid in edits:
                pairs_total += 1
                per_edit_changed[eid][changed_slots(edits["0"], edits[eid])] += 1

    result["original_vs_edit_pairs_measured"] = pairs_total
    yield_report = {}
    for eid, label in [("1", "paraphrase"), ("2", "scope"), ("3", "affirmative")]:
        c = per_edit_changed[eid]
        total = sum(c.values())
        yield_report[f"edit{eid}_{label}"] = {
            "pairs": total,
            "changed_1_sentence": c.get(1, 0),
            "changed_2_sentences": c.get(2, 0),
            "changed_3plus": sum(v for k, v in c.items() if k >= 3),
            "changed_0_sentences_identical_split": c.get(0, 0),
            "single_sentence_rate": round(c.get(1, 0) / total, 4) if total else None,
        }
    result["yield_by_edit_type"] = yield_report

    # Anchor-set yield: passages where BOTH paraphrase (1) and affirmative (3) are single-sentence.
    anchor_ok = 0
    anchor_candidates = 0
    for (split, pid), edits in by_passage.items():
        if "0" in edits and "1" in edits and "3" in edits:
            anchor_candidates += 1
            if changed_slots(edits["0"], edits["1"]) == 1 and changed_slots(edits["0"], edits["3"]) == 1:
                anchor_ok += 1
    result["anchor_sets_with_para_and_affirm"] = anchor_candidates
    result["anchor_sets_both_single_sentence"] = anchor_ok
    result["anchor_yield_rate"] = round(anchor_ok / anchor_candidates, 4) if anchor_candidates else None

    result["payload_sentence_words"] = {
        "n": len(payload_words),
        "mean": round(statistics.mean(payload_words), 1),
        "median": statistics.median(payload_words),
        "p90": sorted(payload_words)[int(0.9 * len(payload_words))],
        "max": max(payload_words),
    }

    deltas = {}
    for k, ref in SECOND_SOURCE.items():
        deltas[k] = {"ours": result.get(k), "second_source": ref, "delta": (result.get(k) or 0) - ref}
    result["two_source_check"] = deltas

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
