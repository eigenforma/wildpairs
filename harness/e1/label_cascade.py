"""E1-P3 label cascade (RUNBOOK R2; A9 resolution: RUN the cascade). Five-class rubric
over Verified-prose Technical g1 pairs (corpus/e1_errata/pairs_g1g2.jsonl, status ==
Verified, type == Technical, code_primary == false): kw2119 / number / polarity-negation /
identifier-constant / scope-other.

  --stage bulk       one pair per call against the Agora llama-server (gpt-oss-20b),
                     temperature 0; the prompt contains ONLY the classification rubric
                     and the two texts - no hypothesis text anywhere.
  --stage arbitrate  the Forge 120B judges ONLY (i) every pair where the bulk label
                     disagrees with the DETERMINISTIC regex label - kw2119/number from
                     the PREREGISTRATION_E1 section-2 pinned definitions (case-sensitive
                     RFC-2119 keyword multiset; \\d+(\\.\\d+)? number multiset), exact
                     instruments, arbitrated in FULL, uncapped - plus every unparseable
                     bulk verdict; and (ii) pairs where bulk names a class the regex
                     cannot see (polarity-negation / identifier-constant / scope-other):
                     DISCLOSED CAP - a seeded sample of 200 of ALL such eligible pairs
                     (seed 20260805), not the full set, to bound 120B wall-clock; the
                     summary block reports the eligible DENOMINATOR beside the 200 and
                     flags every unsampled pair (final label = bulk, flagged unsampled).

ISOLATION RULE (R2): this script REFUSES to run when any argv or environment value
references a PREREGISTRATION file - the labeler must never see hypothesis text; the
rubric below is classification-only.

Mechanics per harness/e1/annotator_errata_120b.py (same servers): harmony-template
workaround - no Output-format section, the verdict is one bare lowercase word, substring
fallback parse; one item per call, temp 0, resumable per item (bulk: append-jsonl resume;
arbitrate: sidecar .arb.jsonl resume). Output: results/<host>/e1_class_cascade.jsonl
(one row per pair: regex flags + bulk + arbitration + final) + .summary.json beside it
(class counts, denominators, cap disclosure, seed). Final-label pin: arbiter verdict
wins where arbitrated (arbiter is blind to both prior labels); regex-agreeing bulk
stands; unsampled pool-(ii) pairs keep bulk, flagged.
"""
import argparse
import json
import os
import random
import re
import sys
import time
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_PAIRS = ROOT / "corpus" / "e1_errata" / "pairs_g1g2.jsonl"

SEED = 20260805
SAMPLE_CAP = 200
CLASSES = ("kw2119", "number", "polarity-negation", "identifier-constant", "scope-other")
WORD2CLASS = {"kw2119": "kw2119", "number": "number", "polarity": "polarity-negation",
              "identifier": "identifier-constant", "scope": "scope-other"}
# Substring fallback scan order (harmony workaround): most-distinctive tokens first.
FALLBACK_ORDER = ("kw2119", "polarity", "identifier", "scope", "number")

# PREREGISTRATION_E1 section 2, pinned instruments, reimplemented exactly:
# case-sensitive multiset over the RFC-2119 keywords (longest alternatives first so
# "MUST NOT" never counts as "MUST"), and the \d+(\.\d+)? number multiset (non-capturing
# group so findall yields full matches).
KW_RE = re.compile(r"\b(MUST NOT|SHALL NOT|SHOULD NOT|NOT RECOMMENDED|MUST|SHALL|SHOULD|"
                   r"REQUIRED|RECOMMENDED|MAY|OPTIONAL)\b")
NUM_RE = re.compile(r"\d+(?:\.\d+)?")

SYSTEM = (
    "You are a blind annotator classifying the difference between two versions of a "
    "sentence from a technical document. Judge only from the two texts given. Choose the "
    "single class that best describes the PRIMARY change from text_A to text_B:\n"
    "kw2119 = a change in RFC-2119 requirement keywords (MUST, MUST NOT, REQUIRED, SHALL, "
    "SHALL NOT, SHOULD, SHOULD NOT, RECOMMENDED, NOT RECOMMENDED, MAY, OPTIONAL).\n"
    "number = a change in a numeric quantity or value (count, size, version, offset, "
    "section number).\n"
    "polarity = a negation or polarity reversal (a 'not' added or removed, an antonym "
    "flip) that is not an RFC-2119 keyword change.\n"
    "identifier = a change to an identifier, field name, constant, code token, protocol "
    "element name, or citation/reference.\n"
    "scope = any other change (wording, qualifiers, applicability, restructuring).\n"
    "Answer with exactly one lowercase word: kw2119, number, polarity, identifier, or "
    "scope. No other text."
)


def refuse_if_prereg_in_context() -> None:
    """R2 isolation rule, literal: no argv or environment value may reference a
    preregistration file. The rubric above is the ONLY prompt content besides the texts."""
    for tok in list(sys.argv) + list(os.environ.values()):
        if "PREREG" in str(tok).upper():
            sys.exit("REFUSING TO RUN (R2 isolation rule): a PREREGISTRATION reference is "
                     "present in argv/env; the labeler must never see hypothesis text")


def kw_multiset(s: str) -> Counter:
    return Counter(KW_RE.findall(s))


def num_multiset(s: str) -> Counter:
    return Counter(NUM_RE.findall(s))


def regex_label(orig: str, corr: str):
    """(kw_changed, num_changed, label). PIN: kw2119 takes precedence when both multisets
    change (both flags are recorded, so the precedence is auditable)."""
    kw = kw_multiset(orig) != kw_multiset(corr)
    num = num_multiset(orig) != num_multiset(corr)
    return kw, num, ("kw2119" if kw else "number" if num else None)


def load_pairs(path: Path):
    pairs, skipped_no_g1 = [], 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r["status"] != "Verified" or r["type"] != "Technical" or r["code_primary"]:
            continue
        if not r["g1_orig"] or not r["g1_corr"]:
            skipped_no_g1 += 1
            continue
        pairs.append((r["pair_id"], r["g1_orig"], r["g1_corr"]))
    if not pairs:
        sys.exit(f"no Verified-prose Technical g1 pairs in {path}")
    return pairs, skipped_no_g1


def ask(base: str, a: str, b: str) -> str:
    """One classification call, temp 0, one bare word back (harmony workaround +
    substring fallback parse, annotator_errata_120b.py pattern)."""
    body = {
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user",
             "content": f"text_A:\n{a}\n\ntext_B:\n{b}\n\nYour one-word verdict:"},
        ],
        "temperature": 0.0,
        "max_tokens": 2048,
    }
    req = urllib.request.Request(base + "/v1/chat/completions",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            content = json.load(r)["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        print("SERVER ERROR BODY:", e.read().decode(errors="replace")[:500], flush=True)
        raise
    low = content.strip().lower()
    if low in WORD2CLASS:
        return WORD2CLASS[low]
    for w in FALLBACK_ORDER:
        if w in low:
            return WORD2CLASS[w]
    return "unparseable"


def read_jsonl_map(path: Path, key: str, val: str):
    out = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                out[r[key]] = r[val]
    return out


def append_row(path: Path, row: dict) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def stage_bulk(base: str, pairs, out_path: Path) -> None:
    done = read_jsonl_map(out_path, "pair_id", "bulk")
    todo = [p for p in pairs if p[0] not in done]
    print(f"bulk: {len(done)} done, {len(todo)} to label", flush=True)
    for k, (pid, a, b) in enumerate(todo):
        t0 = time.time()
        v = ask(base, a, b)
        append_row(out_path, {"pair_id": pid, "bulk": v})
        print(f"[{time.strftime('%H:%M:%S')}] {pid}: {v} ({time.time() - t0:.0f}s) "
              f"[{len(done) + k + 1}/{len(pairs)}]", flush=True)


def stage_arbitrate(base: str, pairs, bulk_path: Path, out_path: Path,
                    skipped_no_g1: int) -> None:
    bulk = read_jsonl_map(bulk_path, "pair_id", "bulk")
    missing = [pid for (pid, _a, _b) in pairs if pid not in bulk]
    if missing:
        sys.exit(f"{len(missing)} pairs have no bulk label (first: {missing[0]}) - "
                 f"finish --stage bulk first")
    rx = {pid: regex_label(a, b) for (pid, a, b) in pairs}
    texts = {pid: (a, b) for (pid, a, b) in pairs}

    disagree = []
    pool_unseen = []
    for (pid, _a, _b) in pairs:
        kw, num, lab = rx[pid]
        bl = bulk[pid]
        if bl == "unparseable":
            disagree.append(pid)
        elif lab is not None and bl != lab:
            disagree.append(pid)
        elif lab is None and bl in ("kw2119", "number"):
            disagree.append(pid)
        elif lab is None and bl in ("polarity-negation", "identifier-constant",
                                    "scope-other"):
            pool_unseen.append(pid)
    sampled = sorted(random.Random(SEED).sample(sorted(pool_unseen),
                                                min(SAMPLE_CAP, len(pool_unseen))))
    selected = sorted(set(disagree) | set(sampled))
    print(f"arbitrate: {len(disagree)} disagreements/unparseable (uncapped) + "
          f"{len(sampled)} sampled of {len(pool_unseen)} regex-unseen-class pairs "
          f"(cap {SAMPLE_CAP}, seed {SEED}) = {len(selected)} calls", flush=True)

    arb_path = out_path.parent / (out_path.name + ".arb.jsonl")
    arb = read_jsonl_map(arb_path, "pair_id", "verdict")
    for k, pid in enumerate(selected):
        if pid in arb:
            continue
        t0 = time.time()
        a, b = texts[pid]
        v = ask(base, a, b)   # arbiter is blind to both prior labels (pin)
        arb[pid] = v
        append_row(arb_path, {"pair_id": pid, "verdict": v})
        print(f"[{time.strftime('%H:%M:%S')}] {pid}: {v} ({time.time() - t0:.0f}s) "
              f"[{len(arb)}/{len(selected)}]", flush=True)

    rows, finals = [], Counter()
    n_unsampled = n_unresolved = 0
    sampled_set, disagree_set = set(sampled), set(disagree)
    for (pid, _a, _b) in pairs:
        kw, num, lab = rx[pid]
        bl = bulk[pid]
        verdict = arb.get(pid)
        if pid in disagree_set or pid in sampled_set:
            reason = "disagreement" if pid in disagree_set else "class_sample"
            if verdict in CLASSES:
                final = verdict
            else:   # unparseable arbiter: fall back, flagged, never silent
                final = bl if bl in CLASSES else (lab or "scope-other")
                n_unresolved += 1
        else:
            reason, verdict = None, None
            if lab is not None:       # regex-agreeing bulk (bl == lab by construction)
                final = lab
            else:                     # regex-unseen class, outside the 200 sample
                final = bl
                n_unsampled += 1
        finals[final] += 1
        rows.append({"pair_id": pid, "kw_changed": kw, "num_changed": num,
                     "regex_label": lab, "bulk": bl, "arbitration_reason": reason,
                     "arbiter": verdict, "final": final,
                     "unsampled": bool(reason is None and lab is None)})
    with out_path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    summary = {
        "population": "Verified-prose Technical g1 pairs (status==Verified, "
                      "type==Technical, code_primary==false, g1 present)",
        "n_pairs": len(pairs), "skipped_no_g1": skipped_no_g1,
        "n_disagreements_arbitrated_uncapped": len(disagree),
        "regex_unseen_class_pool": {"eligible_denominator": len(pool_unseen),
                                    "sampled": len(sampled), "cap": SAMPLE_CAP,
                                    "seed": SEED,
                                    "unsampled_kept_bulk_flagged": n_unsampled},
        "arbiter_unresolved_fallbacks": n_unresolved,
        "final_class_counts": dict(finals),
        "bulk_class_counts": dict(Counter(bulk[pid] for (pid, _a, _b) in pairs)),
        "regex_label_counts": dict(Counter(rx[pid][2] or "none" for (pid, _a, _b) in pairs)),
        "pins": ["kw2119 precedence over number when both multisets change (flags recorded)",
                 "arbiter blind to bulk and regex labels",
                 "arbiter verdict wins where arbitrated; unparseable arbiter falls back "
                 "to bulk (else regex, else scope-other), counted"],
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    sum_path = out_path.parent / (out_path.name + ".summary.json")
    sum_path.write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=1), flush=True)
    print(f"FROZEN {out_path} + {sum_path}", flush=True)


def main(argv=None):
    refuse_if_prereg_in_context()
    ap = argparse.ArgumentParser(description="E1 five-class label cascade (R2)")
    ap.add_argument("--stage", required=True, choices=["bulk", "arbitrate"])
    ap.add_argument("--endpoint", required=True,
                    help="bulk: Agora http://10.1.20.207:8080; arbitrate: Forge "
                         "http://10.1.20.223:8080 (LAN IPs, never bare hostnames)")
    ap.add_argument("--pairs", default=str(DEFAULT_PAIRS))
    ap.add_argument("--in", dest="bulk_in", default=None,
                    help="arbitrate: the completed bulk jsonl")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    pairs, skipped_no_g1 = load_pairs(Path(args.pairs))
    print(f"population: {len(pairs)} Verified-prose Technical g1 pairs "
          f"({skipped_no_g1} skipped without g1)", flush=True)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    base = args.endpoint.rstrip("/")
    if args.stage == "bulk":
        stage_bulk(base, pairs, out_path)
    else:
        if not args.bulk_in:
            sys.exit("--stage arbitrate requires --in <bulk jsonl>")
        stage_arbitrate(base, pairs, Path(args.bulk_in), out_path, skipped_no_g1)


if __name__ == "__main__":
    main()
