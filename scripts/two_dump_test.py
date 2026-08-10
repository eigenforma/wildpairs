#!/usr/bin/env python3
"""
two_dump_test.py -- PREREGISTRATION_E2 SS2(c): is enwiki-20210701 or enwiki-20210720
CondaQA's true source dump?

CHAIN NOTE -- do NOT run until BOTH of these have finished:
  1. scan_condaqa_passages.py has completed (scan_results.jsonl + summary.json exist);
  2. the enwiki-20210720 index download has finished
     (enwiki-20210720-pages-articles-multistream-index.txt.bz2, via wget -c).
  The 20210701 index download must also be complete.

Method: sample 50 matched passages from scan_results.jsonl (seed 20260810;
full-tier passages preferred, topped up from partial-tier only if fewer than 50
full matches exist -- a partial match cannot contain the whole normalized
passage, so full-tier rows carry the discriminating signal). For each sampled
passage's harvested title, resolve the title -> multistream block byte-offset in
BOTH index files, pull ONLY the needed ~100-page bz2 blocks -- a seek+read on
the local 20210701 dump, an HTTP Range GET against archive.org for 20210720 --
and test whether the byte-identical (normalized: same strip_wikitext+lowercase
pipeline as the scan) passage is a substring of that dump's article text.

Output: two_dump_test_results.jsonl (one row per sampled passage:
{passage_id, title, in_20210701, in_20210720, note}) plus a printed verdict
block with the both/only-01/only-20/neither counts.

Titles renamed between the two dumps show up as note="not_in_20210720_index"
and count as absent there.
"""

import bz2
import json
import os
import random
import re
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scan_condaqa_passages import normalize   # identical normalization pipeline

WORKDIR = "/mnt/coldstore/wildpairs/enwiki_scan"
SCAN_RESULTS = os.path.join(WORKDIR, "scan_results.jsonl")
PASSAGES = os.path.join(WORKDIR, "condaqa_passages.jsonl")
LOCAL_DUMP = "/mnt/coldstore/wildpairs/enwiki/enwiki-20210701-pages-articles-multistream.xml.bz2"
IDX_01 = os.path.join(WORKDIR, "enwiki-20210701-pages-articles-multistream-index.txt.bz2")
IDX_20 = os.path.join(WORKDIR, "enwiki-20210720-pages-articles-multistream-index.txt.bz2")
REMOTE_20 = ("https://archive.org/download/enwiki-20210720/"
             "enwiki-20210720-pages-articles-multistream.xml.bz2")
OUT = os.path.join(WORKDIR, "two_dump_test_results.jsonl")

SEED = 20260810
N_SAMPLE = 50
UA = {"User-Agent": "wildpairs-two-dump-test/1.0 (research; contact: local)"}

RE_TEXT = re.compile(r"<text[^>]*>(.*?)</text>", re.DOTALL)


def load_sample():
    rows = [json.loads(l) for l in open(SCAN_RESULTS, encoding="utf-8")]
    full = sorted((r for r in rows if r["tier"] == "full" and r["title"]),
                  key=lambda r: r["passage_id"])
    partial = sorted((r for r in rows if r["tier"] == "partial" and r["title"]),
                     key=lambda r: r["passage_id"])
    rng = random.Random(SEED)
    if len(full) >= N_SAMPLE:
        sample = rng.sample(full, N_SAMPLE)
    else:
        sample = full + rng.sample(partial, min(N_SAMPLE - len(full), len(partial)))
        print(f"[warn] only {len(full)} full-tier matches; "
              f"topped up with {len(sample)-len(full)} partial-tier", flush=True)
    texts = {}
    with open(PASSAGES, encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            texts[row["passage_id"]] = row["text"]
    return sample, texts


def index_blocks(index_bz2, wanted_titles):
    """One streaming pass over a multistream index file.
    Returns {title: (block_offset, next_block_offset_or_None)}."""
    found = {}
    pending = []          # titles whose block ends at the next distinct offset
    last_off = None
    with bz2.open(index_bz2, "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            off_s, _pid, title = line.rstrip("\n").split(":", 2)
            off = int(off_s)
            if off != last_off:
                for t in pending:
                    found[t] = (found[t][0], off)
                pending = []
                last_off = off
            if title in wanted_titles and title not in found:
                found[title] = (off, None)
                pending.append(title)
    return found          # trailing pending keep next_offset=None (read to EOF)


def pages_from_block(block_bytes):
    """Decompress one (or more) bz2 stream(s) -> XML text of ~100 <page> elements."""
    return bz2.decompress(block_bytes).decode("utf-8", errors="replace")


def article_text_from_xml(xml, title):
    """Return the raw (still XML-escaped) <text> content of the page with `title`."""
    import html as _html
    needle = f"<title>{_html.escape(title, quote=False)}</title>"
    for chunk in xml.split("</page>"):
        if needle in chunk:
            m = RE_TEXT.search(chunk)
            return m.group(1) if m else ""
    return None


def fetch_local_block(offset, next_offset):
    with open(LOCAL_DUMP, "rb") as f:
        f.seek(offset)
        n = (next_offset - offset) if next_offset else -1
        return f.read(n)


def fetch_remote_block(offset, next_offset, tries=4):
    end = (next_offset - 1) if next_offset else ""
    req = urllib.request.Request(REMOTE_20, headers={**UA, "Range": f"bytes={offset}-{end}"})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                if resp.status != 206:
                    raise RuntimeError(f"expected 206 Partial Content, got {resp.status}")
                return resp.read()
        except Exception as e:
            if attempt == tries - 1:
                raise
            wait = 5 * (attempt + 1)
            print(f"[retry] range {offset}- : {e}; retrying in {wait}s", flush=True)
            time.sleep(wait)


def main():
    for path in (SCAN_RESULTS, IDX_01, IDX_20):
        if not os.path.exists(path):
            sys.exit(f"missing prerequisite: {path} (see CHAIN NOTE in header)")

    sample, texts = load_sample()
    titles = {r["title"] for r in sample}
    print(f"[start] {len(sample)} sampled passages, {len(titles)} distinct titles", flush=True)

    print("[index] resolving offsets in 20210701 index...", flush=True)
    blk01 = index_blocks(IDX_01, titles)
    print(f"[index] 20210701: {len(blk01)}/{len(titles)} titles resolved", flush=True)
    print("[index] resolving offsets in 20210720 index...", flush=True)
    blk20 = index_blocks(IDX_20, titles)
    print(f"[index] 20210720: {len(blk20)}/{len(titles)} titles resolved", flush=True)

    # group sampled rows by block so each block is fetched exactly once
    def grouped(blocks):
        g = {}
        for r in sample:
            if r["title"] in blocks:
                g.setdefault(blocks[r["title"]], []).append(r)
        return g

    results = {}          # passage_id -> row
    for r in sample:
        results[r["passage_id"]] = {
            "passage_id": r["passage_id"], "title": r["title"], "tier": r["tier"],
            "in_20210701": False, "in_20210720": False, "note": "",
        }

    for (off, nxt), rows in grouped(blk01).items():
        xml = pages_from_block(fetch_local_block(off, nxt))
        for r in rows:
            raw = article_text_from_xml(xml, r["title"])
            if raw is None:
                results[r["passage_id"]]["note"] += "title_not_in_20210701_block;"
                continue
            results[r["passage_id"]]["in_20210701"] = (
                normalize(texts[r["passage_id"]]) in normalize(raw))
    for r in sample:
        if r["title"] not in blk01:
            results[r["passage_id"]]["note"] += "not_in_20210701_index;"

    n_blocks = len(grouped(blk20))
    for i, ((off, nxt), rows) in enumerate(sorted(grouped(blk20).items()), 1):
        xml = pages_from_block(fetch_remote_block(off, nxt))
        for r in rows:
            raw = article_text_from_xml(xml, r["title"])
            if raw is None:
                results[r["passage_id"]]["note"] += "title_not_in_20210720_block;"
                continue
            results[r["passage_id"]]["in_20210720"] = (
                normalize(texts[r["passage_id"]]) in normalize(raw))
        print(f"[remote] block {i}/{n_blocks} (offset {off}) done", flush=True)
        time.sleep(0.3)   # politeness to archive.org
    for r in sample:
        if r["title"] not in blk20:
            results[r["passage_id"]]["note"] += "not_in_20210720_index;"

    both = only01 = only20 = neither = 0
    with open(OUT, "w", encoding="utf-8") as f:
        for pid in sorted(results):
            row = results[pid]
            a, b = row["in_20210701"], row["in_20210720"]
            both += a and b
            only01 += a and not b
            only20 += b and not a
            neither += (not a) and (not b)
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print("=" * 64)
    print(f"[verdict] two-dump test over {len(results)} sampled passages (seed {SEED})")
    print(f"  in both dumps      : {both}")
    print(f"  only 20210701      : {only01}")
    print(f"  only 20210720      : {only20}")
    print(f"  in neither         : {neither}")
    if only01 > only20:
        print("  -> 20210701 is the better-supported source dump")
    elif only20 > only01:
        print("  -> 20210720 is the better-supported source dump")
    else:
        print("  -> sample does not discriminate between the two dumps"
              " (equal support; both plausibly upstream of CondaQA)")
    print("=" * 64, flush=True)


if __name__ == "__main__":
    main()
