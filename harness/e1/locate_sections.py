"""E1-P2 g3: re-locate each erratum's quoted passage in its RFC's full text and expand to
the enclosing section. Best-effort by design; the match rate is disclosed per stratum and
g3 failures drop from g3 analyses only (PREREGISTRATION_E1.md section 2).

Method (deterministic): for each pair, load rfc<N>.txt from the corpus dir (per-doc cache).
Build a whitespace-flexible regex from the first 12 tokens of the normalized quote; find the
first match in the raw file; expand backward/forward to RFC section-heading boundaries
(lines matching ^\\d+(\\.\\d+)*\\.?\\s+\\S or ^(Appendix|Annex)\\s). g3_orig = the section text;
g3_corr = the section with the full quoted span (matched by whole-quote flexible regex when
possible, else the 12-token anchor span) replaced by the correction. Records method used.

Run on the host holding the corpus (agora):
  python3 harness/e1/locate_sections.py /mnt/coldstore/wildpairs/rfc-text
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
PAIRS = ROOT / "corpus" / "e1_errata" / "pairs_g1g2.jsonl"
OUT_PAIRS = ROOT / "corpus" / "e1_errata" / "pairs_g3.jsonl"
OUT_STATS = ROOT / "results" / "verification" / "e1_g3_stats.json"

HEADING = re.compile(r"^(\d+(\.\d+)*\.?\s+\S|Appendix\s+[A-Z]|Annex\s+[A-Z])", re.M)
TOKEN = re.compile(r"\S+")


def flexible(tokens):
    return re.compile(r"\s+".join(re.escape(t) for t in tokens))


def section_span(text: str, lo: int, hi: int):
    starts = [m.start() for m in HEADING.finditer(text)]
    s_lo = 0
    for s in starts:
        if s <= lo:
            s_lo = s
        else:
            break
    s_hi = len(text)
    for s in starts:
        if s >= hi:
            s_hi = s
            break
    return s_lo, s_hi


def main() -> None:
    corpus = Path(sys.argv[1])
    cache = {}
    stats = Counter()
    out = OUT_PAIRS.open("w", encoding="utf-8")
    for line in PAIRS.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        doc = (r["doc_id"] or "").replace("RFC", "").strip()
        key = f"{r['status']}|{r['type']}|{'code' if r['code_primary'] else 'prose'}"
        rec = {"pair_id": r["pair_id"], "doc_id": r["doc_id"], "g3_found": False, "method": None}
        path = corpus / f"rfc{doc}.txt"
        if not doc.isdigit() or not path.exists():
            stats[f"nofile|{key}"] += 1
            out.write(json.dumps(rec) + "\n")
            continue
        if doc not in cache:
            cache[doc] = path.read_text(encoding="utf-8", errors="replace")
        text = cache[doc]
        toks = TOKEN.findall(r["g2_orig"])
        anchor = flexible(toks[:12])
        m = anchor.search(text)
        if not m:
            stats[f"nomatch|{key}"] += 1
            out.write(json.dumps(rec) + "\n")
            continue
        full = flexible(toks) if len(toks) <= 400 else None
        fm = full.search(text, max(0, m.start() - 200)) if full else None
        lo, hi = (fm.start(), fm.end()) if fm else (m.start(), m.end())
        method = "full-quote" if fm else "anchor-12tok"
        s_lo, s_hi = section_span(text, lo, hi)
        sec = text[s_lo:s_hi]
        g3_corr = text[s_lo:lo] + r["g2_corr"] + text[hi:s_hi]
        rec.update({"g3_found": True, "method": method, "g3_orig": sec, "g3_corr": g3_corr,
                    "section_chars": len(sec)})
        stats[f"found-{method}|{key}"] += 1
        out.write(json.dumps(rec, ensure_ascii=False) + "\n")
    out.close()
    total = sum(stats.values())
    found = sum(v for k, v in stats.items() if k.startswith("found"))
    report = {"pairs": total, "g3_found": found, "match_rate": round(found / total, 4),
              "detail": dict(sorted(stats.items()))}
    OUT_STATS.parent.mkdir(parents=True, exist_ok=True)
    OUT_STATS.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"pairs": total, "g3_found": found, "match_rate": report["match_rate"]}, indent=2))


if __name__ == "__main__":
    main()
