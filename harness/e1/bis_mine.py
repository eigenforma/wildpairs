"""E1-P6: mine the bis held-out corpus — RFC-2119 requirement-strength transitions across
direct obsoletes edges. Runs AFTER the errata analysis froze (prereg section 5 sequencing;
scorecard commit is the witness). Encoder-blind: no cosine anywhere here.

Method (prereg-pinned):
- Doc pairs: DIRECT obsoletes edges from the frozen rfc-index.xml (new obsoletes old);
  chains are never skipped — each hop is its own pair.
- Old-side candidates: sentences containing an RFC-2119 keyword (case-sensitive match).
- Alignment: candidate new-side sentences = keyword sentences of the new doc plus sentences
  sharing >=2 non-stopword tokens (inverted index). Best token-Jaccard match wins with an
  ambiguity filter: best >= 0.40 AND (best - second_best) >= 0.10, else the sentence is
  dropped as unalignable (counted).
- Artifact taxonomy, excluded BEFORE labeling (prereg): (a) case-normalization — keyword
  multisets equal after uppercasing ("MUST not" -> "MUST NOT"); (b) exact/whitespace-only
  text matches (no revision); alignment failures counted separately. Subject rewording
  WITHOUT strength change is not an artifact — it is the negative class.
- Positive class: aligned pair whose uppercased RFC-2119 keyword multisets DIFFER
  (strength transition, incl. keyword loss/gain). Negative class: multisets equal, text
  changed (keyword-preserved rewording).

Output: corpus/e1_errata/bis_pairs.jsonl + results/verification/e1_bis_stats.json.
Run on the host holding the frozen RFC corpus:
  python3 harness/e1/bis_mine.py /mnt/coldstore/wildpairs/rfc-text /mnt/coldstore/wildpairs/rfc-index.xml
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parent.parent.parent
OUT_PAIRS = ROOT / "corpus" / "e1_errata" / "bis_pairs.jsonl"
OUT_STATS = ROOT / "results" / "verification" / "e1_bis_stats.json"

KW = re.compile(r"\b(MUST NOT|SHALL NOT|SHOULD NOT|NOT RECOMMENDED|MUST|REQUIRED|SHALL|SHOULD|RECOMMENDED|MAY|OPTIONAL)\b")
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
TOKEN = re.compile(r"[a-z0-9]+")
STOP = set("the a an of to in for is are be and or as by on with that this it its".split())


def sentences(text: str):
    flat = re.sub(r"\s+", " ", text)
    return [s.strip() for s in SENT_SPLIT.split(flat) if 30 <= len(s.strip()) <= 600]


def toks(s: str):
    return set(TOKEN.findall(s.lower())) - STOP


def kw_multiset(s: str) -> Counter:
    return Counter(k.upper() for k in KW.findall(s))


def jac(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if (a or b) else 1.0


def main() -> None:
    corpus, index_path = Path(sys.argv[1]), Path(sys.argv[2])
    ns = {"r": "https://www.rfc-editor.org/rfc-index"}
    tree = ElementTree.parse(index_path)
    edges = []
    for entry in tree.getroot().findall("r:rfc-entry", ns):
        new_id = entry.findtext("r:doc-id", "", ns)
        obs = entry.find("r:obsoletes", ns)
        if obs is not None:
            for d in obs.findall("r:doc-id", ns):
                edges.append((d.text, new_id))
    edges = sorted(set(edges))

    stats = Counter()
    out = OUT_PAIRS.open("w", encoding="utf-8")
    n_docpairs = 0
    for old_id, new_id in edges:
        po = corpus / (old_id.lower().replace("rfc", "rfc") + ".txt")
        pn = corpus / (new_id.lower() + ".txt")
        po = corpus / f"{old_id.lower()}.txt"
        if not po.exists() or not pn.exists():
            stats["docpair_missing_text"] += 1
            continue
        n_docpairs += 1
        old_sents = [s for s in sentences(po.read_text(encoding="utf-8", errors="replace")) if KW.search(s)]
        new_all = sentences(pn.read_text(encoding="utf-8", errors="replace"))
        new_kw_idx = [i for i, s in enumerate(new_all) if KW.search(s)]
        inv = defaultdict(set)
        for i, s in enumerate(new_all):
            for t in toks(s):
                inv[t].add(i)
        new_toks = {i: toks(s) for i, s in enumerate(new_all)}
        for os_ in old_sents:
            ot = toks(os_)
            cand = set(new_kw_idx)
            share = Counter()
            for t in ot:
                for i in inv.get(t, ()):
                    share[i] += 1
            cand |= {i for i, c in share.items() if c >= 2}
            if not cand:
                stats["old_sentence_no_candidates"] += 1
                continue
            scored = sorted(((jac(ot, new_toks[i]), i) for i in cand), reverse=True)
            best, bi = scored[0]
            second = scored[1][0] if len(scored) > 1 else 0.0
            if best < 0.40 or (best - second) < 0.10:
                stats["old_sentence_ambiguous_or_weak"] += 1
                continue
            ns_ = new_all[bi]
            if re.sub(r"\s+", " ", os_) == re.sub(r"\s+", " ", ns_):
                stats["identical_no_revision"] += 1
                continue
            mo, mn = kw_multiset(os_), kw_multiset(ns_)
            raw_mo = Counter(KW.findall(os_))
            raw_mn = Counter(KW.findall(ns_))
            if mo == mn and raw_mo != raw_mn:
                stats["artifact_case_normalization"] += 1
                continue
            label = "strength_transition" if mo != mn else "keyword_preserved_rewording"
            stats[label] += 1
            out.write(json.dumps({
                "pair_id": f"bis-{old_id}-{new_id}-{stats[label]}",
                "old_doc": old_id, "new_doc": new_id,
                "old_sentence": os_, "new_sentence": ns_,
                "label": label,
                "kw_old": dict(mo), "kw_new": dict(mn),
                "align_jaccard": round(best, 4),
            }, ensure_ascii=False) + "\n")
    out.close()
    report = {"direct_obsoletes_edges": len(edges), "docpairs_with_text": n_docpairs, **stats}
    OUT_STATS.parent.mkdir(parents=True, exist_ok=True)
    OUT_STATS.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
